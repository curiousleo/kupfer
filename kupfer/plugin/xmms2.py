# vim: noexpandtab 

__kupfer_name__ = _("XMMS2")
__kupfer_sources__ = ("XMMS2Source", )
__description__ = _("Play and enqueue tracks and browse the music library")
__version__ = "2011-03-19"
__author__ = "Leonhard Markert <leo.markert@web.de>"

# This implementation depends on the command-line tool "nyxmms2",
# which should come with XMMS2 by default.

# TODO: Add shuffle, repeat settings
# TODO: Add playlist support
# TODO: Thunderbird plugin: Multiple recipients -- send to list of people

import itertools
import gio
import urllib
from os import path as os_path

try:
	from mutagen.mp3 import MP3
	from mutagen.mp4 import MP4
	_MUTAGEN = True
except(ImportError):
	_MUTAGEN = False

from kupfer.objects import (Leaf, Source, AppLeaf, Action, RunnableLeaf,
		SourceLeaf )
from kupfer import objects, icons, utils, config
from kupfer.obj.apps import AppLeafContentMixin
from kupfer import plugin_support
from kupfer.plugin import xmms2_support

from time import sleep # FIXME: Needed for ugly hack

__kupfer_settings__ = plugin_support.PluginSettings(
	{
		"key" : "toplevel_artists",
		"label": _("Include artists in top level"),
		"type": bool,
		"value": True,
	},
	{
		"key" : "toplevel_albums",
		"label": _("Include albums in top level"),
		"type": bool,
		"value": False,
	},
	{
		"key" : "toplevel_songs",
		"label": _("Include songs in top level"),
		"type": bool,
		"value": False,
	},
)

XMMS2 = "nyxmms2"

def play_song(info):
	song_id = info["id"]
	utils.spawn_async((XMMS2, "add", "id:%s" % song_id))
	# FIXME: Ugly hack that ensure that the song is first added
	# so we can jump to it afterwards.
	sleep(0.1)
	utils.spawn_async((XMMS2, "jump", "id:%s" % song_id))
	# start playing
	utils.spawn_async((XMMS2, "play"))

def enqueue_songs(info, clear_queue=False):
	songs = list(info)
	if not songs:
		return
	if clear_queue:
		utils.spawn_async((XMMS2, "playlist", "clear"))
	for song in songs:
		song_id = song["id"]
		utils.spawn_async((XMMS2, "add", "id:%s" % song_id))

class Play (RunnableLeaf):
	def __init__(self):
		RunnableLeaf.__init__(self, name=_("Play"))
	def run(self):
		utils.spawn_async((XMMS2, "play"))
	def get_description(self):
		return _("Resume playback in XMMS2")
	def get_icon_name(self):
		return "media-playback-start"

class Pause (RunnableLeaf):
	def __init__(self):
		RunnableLeaf.__init__(self, name=_("Pause"))
	def run(self):
		utils.spawn_async((XMMS2, "pause"))
	def get_description(self):
		return _("Pause playback in XMMS2")
	def get_icon_name(self):
		return "media-playback-pause"

class Next (RunnableLeaf):
	def __init__(self):
		RunnableLeaf.__init__(self, name=_("Next"))
	def run(self):
		utils.spawn_async((XMMS2, "next"))
	def get_description(self):
		return _("Jump to next track in XMMS2")
	def get_icon_name(self):
		return "media-skip-forward"

class Previous (RunnableLeaf):
	def __init__(self):
		RunnableLeaf.__init__(self, name=_("Previous"))
	def run(self):
		utils.spawn_async((XMMS2, "prev"))
	def get_description(self):
		return _("Jump to previous track in XMMS2")
	def get_icon_name(self):
		return "media-skip-backward"

# TODO: Implement nice song notifier using notify-send
# class ShowPlaying (RunnableLeaf):
# 	def __init__(self):
# 		RunnableLeaf.__init__(self, name=_("Show Playing"))
# 	def run(self):
# 		utils.spawn_async((XMMS2, "--no-start", "--notify"))
# 	def get_description(self):
# 		return _("Tell which song is currently playing")
# 	def get_gicon(self):
# 		return icons.ComposedIcon("dialog-information", "audio-x-generic")
# 	def get_icon_name(self):
# 		return "dialog-information"

class ClearQueue (RunnableLeaf):
	def __init__(self):
		RunnableLeaf.__init__(self, name=_("Clear Queue"))
	def run(self):
		utils.spawn_async((XMMS2, "playlist", "clear"))
	def get_icon_name(self):
		return "edit-clear"

def _songs_from_leaf(leaf):
	"return a sequence of songs from @leaf"
	if isinstance(leaf, SongLeaf):
		return (leaf.object, )
	if isinstance(leaf, TrackCollection):
		return list(leaf.object)

class PlayTracks (Action):
	rank_adjust = 5
	def __init__(self):
		Action.__init__(self, _("Play"))

	def activate(self, leaf):
		self.activate_multiple((leaf, ))

	def activate_multiple(self, objects):
		# for multiple dispatch, play the first and enqueue the rest
		to_enqueue = []
		objects = iter(objects)
		# take only the first object in the first loop
		# notice the break
		for leaf in objects:
			songs = _songs_from_leaf(leaf)
			if not songs:
				continue
			play_song(songs[0])
			to_enqueue.extend(songs[1:])
			break
		for leaf in objects:
			to_enqueue.extend(_songs_from_leaf(leaf))
		if to_enqueue:
			enqueue_songs(to_enqueue, clear_queue=True)

	def get_description(self):
		return _("Play tracks in XMMS2")
	def get_icon_name(self):
		return "media-playback-start"

class Enqueue (Action):
	def __init__(self):
		Action.__init__(self, _("Enqueue"))
	def activate(self, leaf):
		self.activate_multiple((leaf, ))

	def activate_multiple(self, objects):
		to_enqueue = []
		for leaf in objects:
			to_enqueue.extend(_songs_from_leaf(leaf))
		enqueue_songs(to_enqueue)

	def get_description(self):
		return _("Add tracks to the play queue")
	def get_gicon(self):
		return icons.ComposedIcon("gtk-execute", "media-playback-start")
	def get_icon_name(self):
		return "media-playback-start"

class SongLeaf (Leaf):
	serializable = 1
	def __init__(self, info, name=None):
		"""Init with song info
		@info: Song information dictionary
		"""
		if not name: name = info["title"]
		Leaf.__init__(self, info, name)
	def repr_key(self):
		"""To distinguish songs by the same name"""
		return (self.object["title"], self.object["artist"],
				self.object["album"])
	def get_actions(self):
		yield PlayTracks()
		yield Enqueue()
	def get_description(self):
		# TRANS: Song description
		return _("by %(artist)s from %(album)s") % {
				"artist": self.object["artist"],
				"album": self.object["album"],
				}
	def get_icon_name(self):
		return "audio-x-generic"

class CollectionSource (Source):
	def __init__(self, leaf):
		Source.__init__(self, unicode(leaf))
		self.leaf = leaf
	def get_items(self):
		for song in self.leaf.object:
			yield SongLeaf(song)
	def repr_key(self):
		return self.leaf.repr_key()
	def get_description(self):
		return self.leaf.get_description()
	def get_thumbnail(self, w, h):
		return self.leaf.get_thumbnail(w, h)
	def get_gicon(self):
		return self.leaf.get_gicon()
	def get_icon_name(self):
		return self.leaf.get_icon_name()

class TrackCollection (Leaf):
	"""A generic track collection leaf, such as one for
	an Album or an Artist
	"""
	def __init__(self, info, name):
		"""Init with track collection
		@info: Should be a sequence of song information dictionaries
		"""
		Leaf.__init__(self, info, name)
	def get_actions(self):
		yield PlayTracks()
		yield Enqueue()
	def has_content(self):
		return True
	def content_source(self, alternate=False):
		return CollectionSource(self)
	def get_icon_name(self):
		return "media-optical"

class AlbumLeaf (TrackCollection):
	def get_description(self):
		artist = None
		for song in self.object:
			if not artist:
				artist = song["artist"]
			elif artist != song["artist"]:
				# TRANS: Multiple artist description "Artist1 et. al. "
				artist = _("%s et. al.") % artist
			break
		# TRANS: Album description "by Artist"
		return _("by %s") % (artist, )

	def _get_thumb_local(self):
		# try local filesystem
		uri = urllib.unquote_plus(str(self.object[0]["url"]))
		gfile = gio.File(uri)
		cover_names = ("album.jpg", "cover.jpg", ".folder.jpg")
		for cover_name in cover_names:
			cfile = gfile.resolve_relative_path("../" + cover_name)
			if cfile.query_exists():
				return cfile.get_path()

	def _get_thumb_metadata(self):
		# Using mutagen
		# FIXME: This is ugly
		# TODO: Add ogg vorbis, flac, ... 
		uri = urllib.unquote_plus(str(self.object[0]["url"])).replace("file://", "")
		ext = os_path.splitext(uri)[1][1:].lower()
		if (ext == "m4a" or ext == "mp4" or ext == "aac"):
			mp4info = MP4(uri)
			try:
				pic = mp4info["covr"][0]
			except(KeyError):
				return None
		elif ext == "mp3":
			# add mime type differentiation
			mp3info = MP3(uri)
			try:
				pic = str(mp3info.tags.getall("APIC")[0].data)
			except(IndexError):
				return None

		return pic

	def get_thumbnail(self, width, height):
		# FIXME: This is ugly and does not work the way I expect
		if not (hasattr(self, "cover_data") or hasattr(self, "cover_file")):
			cover_file = self._get_thumb_local()
			if cover_file:
				self.cover_file = cover_file
			if _MUTAGEN and not hasattr(self, "cover_file"):
				cover_data = self._get_thumb_metadata()
				if cover_data:
					self.cover_data = cover_data

		if   hasattr(self, "cover_file"): return icons.get_pixbuf_from_file(self.cover_file, width, height)
		elif hasattr(self, "cover_data"): return icons.get_pixbuf_from_data(self.cover_data, width, height)

class ArtistAlbumsSource (CollectionSource):
	def get_items(self):
		albums = {}
		for song in self.leaf.object:
			album = song["album"]
			album_list = albums.get(album, [])
			album_list.append(song)
			albums[album] = album_list
		for album in albums:
			yield AlbumLeaf(albums[album], album)
	def should_sort_lexically(self):
		return True

class ArtistLeaf (TrackCollection):
	def get_description(self):
		# TRANS: Artist songs collection description
		return _("Tracks by %s") % (unicode(self), )
	def get_gicon(self):
		return icons.ComposedIcon("media-optical", "system-users")
	def content_source(self, alternate=False):
		if alternate:
			return CollectionSource(self)
		return ArtistAlbumsSource(self)

class XMMS2AlbumsSource (Source):
	def __init__(self, library):
		Source.__init__(self, _("Albums"))
		self.library = library
	
	def get_items(self):
		for album in self.library:
			yield AlbumLeaf(self.library[album], album)
	def should_sort_lexically(self):
		return True

	def get_description(self):
		return _("Music albums in XMMS2 Library")
	def get_gicon(self):
		return icons.ComposedIcon("xmms2", "media-optical",
				emblem_is_fallback=True)
	def get_icon_name(self):
		return "xmms2"
	def provides(self):
		yield AlbumLeaf

class XMMS2ArtistsSource (Source):
	def __init__(self, library):
		Source.__init__(self, _("Artists"))
		self.library = library

	def get_items(self):
		for artist in self.library:
			yield ArtistLeaf(self.library[artist], artist)
	def should_sort_lexically(self):
		return True

	def get_description(self):
		return _("Music artists in XMMS2 Library")
	def get_gicon(self):
		return icons.ComposedIcon("xmms2", "system-users",
				emblem_is_fallback=True)
	def get_icon_name(self):
		return "xmms2"
	def provides(self):
		yield ArtistLeaf

def _locale_sort_artist_album_songs(artists):
	"""Locale sort dictionary @artists by Artist, then Album;
	each artist in @artists should already contain songs
	grouped by album and sorted by track number.
	"""
	for artist in utils.locale_sort(artists):
		artist_songs = artists[artist]
		albums = {}
		albumkey = lambda song: song["album"]
		for album, songs in itertools.groupby(artist_songs, albumkey):
			albums[album] = list(songs)
		for album in utils.locale_sort(albums):
			for song in albums[album]:
				yield song

class XMMS2SongsSource (Source):
	"""The whole song library in Leaf representation"""
	def __init__(self, library):
		Source.__init__(self, _("Songs"))
		self.library = library

	def get_items(self):
		for song in _locale_sort_artist_album_songs(self.library):
			yield SongLeaf(song)

	def get_actions(self):
		return ()
	def get_description(self):
		return _("Songs in XMMS2 library")
	def get_gicon(self):
		return icons.ComposedIcon("xmms2", "audio-x-generic",
				emblem_is_fallback=True)
	def provides(self):
		yield SongLeaf

class XMMS2Source (AppLeafContentMixin, Source):
	appleaf_content_id = "xmms2"
	def __init__(self):
		Source.__init__(self, _("XMMS2"))
	def get_items(self):
		try:
			dbfile = xmms2_support.get_xmms2_dbfile()
			if dbfile: songs = xmms2_support.get_xmms2_songs(dbfile)
		except StandardError, e:
			self.output_error(e)
			songs = []

		albums = xmms2_support.parse_xmms2_albums(songs)
		artists = xmms2_support.parse_xmms2_artists(songs)
		yield Play()
		yield Pause()
		yield Next()
		yield Previous()
		yield ClearQueue()
		# yield ShowPlaying()
		artist_source = XMMS2ArtistsSource(artists)
		album_source = XMMS2AlbumsSource(albums)
		songs_source = XMMS2SongsSource(artists)
		yield SourceLeaf(artist_source)
		yield SourceLeaf(album_source)
		yield SourceLeaf(songs_source)
		# we use get_leaves here to get sorting etc right
		if __kupfer_settings__["toplevel_artists"]:
			for leaf in artist_source.get_leaves():
				yield leaf
		if __kupfer_settings__["toplevel_albums"]:
			for leaf in album_source.get_leaves():
				yield leaf
		if __kupfer_settings__["toplevel_songs"]:
			for leaf in songs_source.get_leaves():
				yield leaf

	def get_description(self):
		return _("Play and enqueue tracks and browse the music library")
	def get_icon_name(self):
		return "xmms2"
	def provides(self):
		yield RunnableLeaf
		yield SourceLeaf
		yield SongLeaf

# vim: noexpandtab 

__kupfer_name__ = _("XMMS2")
__kupfer_sources__ = ("XMMS2Source", )
__description__ = _("Play and enqueue tracks and browse the music library")
__version__ = ""
__author__ = "Leonhard Markert <curiousleo@ymail.com>"

# This code is heavily based on Ulrik Sverdrup's Rhythmbox Plugin

# This implementation depends on the command-line tool "nyxmms2",
# which should come with XMMS2 by default.

# TODO: Add playlist support

import itertools
import gio, glib
import urllib
import sqlite3
import subprocess
from os import path as os_path
from contextlib import closing

try:
	import mutagen
	_MUTAGEN = True
except(ImportError):
	_MUTAGEN = False

from kupfer.objects import (Leaf, Source, AppLeaf, Action, RunnableLeaf,
		SourceLeaf )
from kupfer import objects, icons, utils, uiutils, config
from kupfer.obj.apps import AppLeafContentMixin
from kupfer import plugin_support
from kupfer.plugin import rhythmbox_support

XMMS2 = "nyxmms2"
NEEDED_KEYS= ("id", "title", "artist", "album", "tracknr", "url")

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

def get_xmms2_songs(dbfile):
	"""Get songs from xmms2 media library (sqlite). Generator function."""
	with closing(sqlite3.connect(dbfile, timeout=2)) as db:
		cu = db.execute("""
				SELECT A.id, A.value,    B.value,           C.value,          D.value,            E.value
				FROM   Media A,          Media B,           Media C,          Media D,            Media E
				WHERE  A.key="title" AND B.key="artist" AND C.key="album" AND D.key="tracknr" AND E.key="url"
				AND    A.id = B.id AND B.id = C.id AND C.id = D.id AND D.id = E.id
		""")

		for row in cu:
			# NEEDED_KEYS and returned rows must have the same order for this to work
			song = dict(zip((NEEDED_KEYS), row))
			# URLs are saved in quoted format in the db; they're also latin1 encoded but returned as unicode
			song["url"] = _unicode_url(song["url"])
			# Generator
			yield song

def _unicode_url(rawurl):
	return urllib.unquote_plus(rawurl).encode('latin1').decode('utf-8')

def get_current_song():
	"""Returns the current song as a dict"""
	for line in _cmd_output(["list"]):
		if line.startswith("->"):
			return _parse_line(line)

def get_playlist_songs():
	"""Yield the IDs of all songs in the current playlist"""
	for line in _cmd_output(["list"]):
		if line.startswith("  [") or line.startswith("->["):
			song = _parse_line(line)
			yield song["id"]

def _cmd_output(args):
	toolProc = subprocess.Popen([XMMS2] + args, stdout=subprocess.PIPE)
	stdout, stderr = toolProc.communicate()
	return stdout.splitlines()

def _parse_line(line):
	# nyxmms2 list output format:
	# ->[5/295] Lily Allen - I Could Say (04:05)
	song = {}
	song["id"] = int(line[line.find("/") + 1:line.find("]")])
	song["artist"] = line[line.find("]") + 2:line.find(" - ")]
	song["title"] = line[line.find(" - ") + 3:line.rfind(" (")]
	return song

def play_song(info):
	song_id = info["id"]
	if song_id in get_playlist_songs():
		_jump_and_play(song_id); return

	utils.spawn_async((XMMS2, "add", "id:%d" % song_id))
	# Ensure that the song is first added so we can jump to it afterwards.
	glib.timeout_add(100, _jump_and_play, song_id)

def _jump_and_play(song_id):
	utils.spawn_async((XMMS2, "jump", "id:%d" % song_id))
	utils.spawn_async((XMMS2, "play"))
	# must return False so it's not called again
	return False

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

class ShowPlaying (RunnableLeaf):
	def __init__(self):
		RunnableLeaf.__init__(self, name=_("Show Playing"))
	def run(self):
		song = get_current_song()
		uiutils.show_notification(title=song["artist"], text=song["title"])
	def get_description(self):
		return _("Tell which song is currently playing")
	def get_gicon(self):
		return icons.ComposedIcon("dialog-information", "audio-x-generic")
	def get_icon_name(self):
		return "dialog-information"

class ClearQueue (RunnableLeaf):
	def __init__(self):
		RunnableLeaf.__init__(self, name=_("Clear Queue"))
	def run(self):
		utils.spawn_async((XMMS2, "playlist", "clear"))
	def get_icon_name(self):
		return "edit-clear"

class ToggleRepeat (RunnableLeaf):
	def __init__(self):
		RunnableLeaf.__init__(self, name=_("Repeat"))
	def run(self):
		toggle = int(
			_cmd_output("server config playlist.repeat_all".split(" "))[0][-1])
		toggle = (toggle + 1) % 2
		utils.spawn_async(([XMMS2] + ("server config playlist.repeat_all %d" % toggle).split(" ")))
	def get_description(self):
		return _("Toggle repeat playlist in XMMS2")
	def get_icon_name(self):
		# FIXME: This is not the correct icon
		return "edit-undo"

class Shuffle (RunnableLeaf):
	def __init__(self):
		RunnableLeaf.__init__(self, name=_("Shuffle"))
	def run(self):
		utils.spawn_async(([XMMS2] + "playlist shuffle".split(" ")))
	def get_description(self):
		return _("Shuffle playlist in XMMS2")
	# def get_icon_name(self):
		# FIXME: Find correct icon

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
		"Reads album art from image files in music folder."
		# gio.File needs encoded filename
		fpath = self.object[0]["url"].encode("utf-8")
		gfile = gio.File(fpath)
		cover_names = ("album.jpg", "cover.jpg", ".folder.jpg")
		for cover_name in cover_names:
			cfile = gfile.resolve_relative_path("../" + cover_name)
			if cfile.query_exists():
				return cfile.get_path()

	def _get_thumb_metadata(self):
		"Reads album art from metadata."
		pic = ""
		pics = []

		# mutagen uses file() to read the tags
		# file() can only read local files and uses path, not url
		fpath = self.object[0]["url"].replace("file://", "")

		finfo = mutagen.File(fpath)
		if isinstance(finfo, mutagen.mp3.MP3):
			pics = (apic.data for apic in finfo.tags.getall("APIC"))
		elif isinstance(finfo, mutagen.mp4.MP4):
			pics = finfo.tags.get("covr")
		elif isinstance(finfo, mutagen.flac.FLAC):
			pics = (apic.data for apic in finfo.pictures)

		try:
			pic = max(pics)
			return pic
		except(ValueError, TypeError): pass

	def get_thumbnail(self, width, height):
		if not (hasattr(self, "cover_data") or hasattr(self, "cover_file")):
			cover_file = self._get_thumb_local()
			if cover_file:
				self.cover_file = cover_file
			if _MUTAGEN and not hasattr(self, "cover_file"):
				cover_data = self._get_thumb_metadata()
				if cover_data:
					self.cover_data = cover_data

		try:
			if hasattr(self, "cover_file"):
				return icons.get_pixbuf_from_file(self.cover_file, width, height)
			elif hasattr(self, "cover_data"):
				return icons.get_pixbuf_from_data(self.cover_data, width, height)
		except(glib.GError):
			pass

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
			dbfile = config.get_config_file("medialib.db", package="xmms2")
			songs = list(get_xmms2_songs(dbfile))
		except StandardError, e:
			self.output_error(e)
			songs = []

		albums = rhythmbox_support.parse_rhythmbox_albums(songs)
		artists = rhythmbox_support.parse_rhythmbox_artists(songs)
		yield Play()
		yield Pause()
		yield Next()
		yield Previous()
		yield ClearQueue()
		yield ToggleRepeat()
		yield Shuffle()
		yield ShowPlaying()
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


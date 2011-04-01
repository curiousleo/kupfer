# vim: noexpandtab 

# This code is heavily based on Ulrik Sverdrup's Rhythmbox Plugin

# This implementation depends on the command-line tool "nyxmms2",
# which should come with XMMS2 by default.

from os import path as os_path
import sqlite3
import urllib

NEEDED_KEYS= ("id", "title", "artist", "album", "tracknr", "url")

def _tourl(rawurl):
	return urllib.unquote_plus(rawurl).encode('latin1').decode('utf-8')

def get_xmms2_dbfile():
	"""Returns default path of xmms2 media library if it exists"""
	dbfile = os_path.expanduser("~/.config/xmms2/medialib.db")
	if os_path.exists(dbfile):
		return dbfile

def get_xmms2_songs(dbfile):
	"""Get songs from xmms2 media library (sqlite). Generator function."""
	db = sqlite3.connect(dbfile)
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
		song["url"] = _tourl(song["url"])
		# Generator
		yield song

	db.close()

def sort_album(album):
	"""Sort album in track order"""
	def get_track_number(rec):
		try:
			tnr = int(rec["tracknr"])
		except (KeyError, ValueError):
			tnr = 0
		return tnr
	album.sort(key=get_track_number)

def sort_album_order(songs):
	"""Sort songs in order by album then by track number

	>>> songs = [
	... {"title": "a", "album": "B", "tracknr": "2"},
	... {"title": "b", "album": "A", "tracknr": "1"},
	... {"title": "c", "album": "B", "tracknr": "1"},
	... ]
	>>> sort_album_order(songs)
	>>> [s["title"] for s in songs]
	['b', 'c', 'a']
	"""
	pass

	def get_album_order(rec):
		try:
			tnr = int(rec["tracknr"])
		except (KeyError, ValueError):
			tnr = 0
		return (rec["album"], tnr)
	songs.sort(key=get_album_order)

def parse_xmms2_albums(songs):
	albums = {}
	for song in songs:
		song_artist = song["artist"]
		if not song_artist:
			continue
		song_album = song["album"]
		if not song_album:
			continue
		album = albums.get(song_album, [])
		album.append(song)
		albums[song_album] = album
	# sort album in track order
	for album in albums:
		sort_album(albums[album])
	return albums

def parse_xmms2_artists(songs):
	artists = {}
	for song in songs:
		song_artist = song["artist"]
		if not song_artist:
			continue
		artist = artists.get(song_artist, [])
		artist.append(song)
		artists[song_artist] = artist
	# sort in album + track order
	for artist in artists:
		sort_album_order(artists[artist])
	return artists

if __name__ == '__main__':
	import doctest
	doctest.testmod()

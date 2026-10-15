"""MusicLibrary (STUB: frozen interface; Builder D replaces the body)."""
import hashlib


def track_id(path):
    return hashlib.sha1(path.encode("utf-8")).hexdigest()[:16]


class MusicLibrary:
    def __init__(self, music_dir=None, index_path=None):
        self.music_dir = music_dir

    def start_scan(self, on_progress=None, on_done=None):
        if on_done:
            on_done()

    def is_scanning(self):
        return False

    def get_tracks(self):
        return []

    def get_artists(self):
        return []

    def get_albums(self, artist=None):
        return []

    def tracks_for_artist(self, name):
        return []

    def tracks_for_album(self, title, artist):
        return []

    def search(self, query, kind="all"):
        return {"songs": [], "artists": [], "albums": []}

    def get_art(self, track, size):
        return None


class MockMusicLibrary(MusicLibrary):
    pass

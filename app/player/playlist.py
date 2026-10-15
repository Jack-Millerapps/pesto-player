"""
Playlists stored as one JSON file each under config.PLAYLIST_DIR (~/.pesto/playlists).

A file holds the playlist name plus a compact copy of each track, so playlists load
without waiting for a library scan. Names are mapped to safe filenames (no path
separators, nothing outside PLAYLIST_DIR). Writes are atomic.
"""

import json
import os
import re

import config

_KEEP = ("id", "path", "title", "artist", "album", "duration", "track_no")


def _fname(name):
    stem = re.sub(r"[^\w\- .()&']", "_", name.strip(), flags=re.UNICODE).strip(" .")
    if not stem:
        raise ValueError("empty playlist name")
    return stem[:80] + ".json"


class PlaylistStore:
    def __init__(self, directory=None):
        self.directory = os.path.expanduser(directory or config.PLAYLIST_DIR)

    def _path(self, name):
        return os.path.join(self.directory, _fname(name))

    def _read(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("tracks"), list):
                return data
        except (OSError, ValueError):
            pass
        return None

    def list_names(self):
        try:
            files = os.listdir(self.directory)
        except OSError:
            return []
        names = []
        for fn in files:
            if fn.endswith(".json"):
                data = self._read(os.path.join(self.directory, fn))
                if data and data.get("name"):
                    names.append(data["name"])
        return sorted(names, key=str.casefold)

    def load(self, name):
        try:
            data = self._read(self._path(name))
        except ValueError:
            return []
        if not data:
            return []
        return [dict(t) for t in data["tracks"] if isinstance(t, dict) and t.get("path")]

    def save(self, name, tracks):
        path = self._path(name)
        os.makedirs(self.directory, exist_ok=True)
        payload = {"name": name.strip(),
                   "tracks": [{k: t.get(k) for k in _KEEP} for t in tracks]}
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.replace(tmp, path)

    def delete(self, name):
        try:
            os.remove(self._path(name))
        except (OSError, ValueError):
            pass

    def add(self, name, track):
        tracks = self.load(name)
        if any(t.get("id") == track.get("id") for t in tracks):
            return
        tracks.append(track)
        self.save(name, tracks)

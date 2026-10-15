"""
Music library for Pesto Player.

- start_scan() walks the music dir on a background thread and never blocks the UI.
- Metadata is cached in a JSON index keyed by (path, mtime, size), so rescans of
  an unchanged library only stat() files.
- Extensions are matched case-insensitively; hidden dirs (e.g. ~/Music/.incoming,
  where the uploader stages half-written files) are skipped.
- Everything the UI reads (tracks, artists, albums, search index) is built once
  per scan and swapped in atomically, so screens never see a half-built state.
"""

import hashlib
import io
import json
import os
import re
import threading
from collections import OrderedDict

import config

try:
    from mutagen import File as MutagenFile
    MUTAGEN_AVAILABLE = True
except ImportError:  # pragma: no cover
    MutagenFile = None
    MUTAGEN_AVAILABLE = False

UNKNOWN_ARTIST = "Unknown Artist"
UNKNOWN_ALBUM = "Unknown Album"
SIDECAR_STEMS = ("cover", "folder", "front", "album")
SIDECAR_EXTS = (".jpg", ".jpeg", ".png")
INDEX_VERSION = 1
ART_CACHE_BYTES = 8 * 1024 * 1024   # bound by pixel memory, not entry count (sizes vary 40-200 px)
ART_CACHE_MAX_ENTRIES = 1024         # also bounds cached "no art" (None) results


def track_id(path):
    """Stable id: hash of the path (survives rescans and restarts)."""
    return hashlib.sha1(path.encode("utf-8", "surrogateescape")).hexdigest()[:16]


_CTRL = re.compile(r"[\x00-\x1f\x7f]")


def clean_text(value):
    r"""Make a tag/filename safe to render: undo surrogateescape (os.walk gives
    'bad\udcffname' for non-UTF-8 filenames), drop NUL/control characters."""
    if value is None:
        return ""
    s = str(value)
    try:
        s.encode("utf-8")
    except UnicodeEncodeError:
        s = s.encode("utf-8", "surrogateescape").decode("utf-8", "replace")
    return _CTRL.sub("", s).strip()


def _first(v):
    if isinstance(v, (list, tuple)):
        v = v[0] if v else None
    return (clean_text(v) or None) if v not in (None, "") else None


def _track_no(v):
    v = _first(v)
    if not v:
        return None
    try:
        return int(v.split("/")[0])
    except ValueError:
        return None


class MusicLibrary:
    def __init__(self, music_dir=None, index_path=None):
        self.music_dir = os.path.expanduser(music_dir or config.MUSIC_DIRECTORY)
        self.index_path = index_path or config.INDEX_FILE
        self._exts = tuple(e.lower() for e in config.SUPPORTED_FORMATS)
        self._lock = threading.Lock()
        self._scan_thread = None
        self._tracks = []
        self._artists = []
        self._albums = []
        self._by_artist = {}
        self._by_album = {}
        self._search_idx = []
        self._art_cache = OrderedDict()   # (track id, size) -> Surface | None
        self._art_bytes = 0
        self._art_lock = threading.Lock()
        self._art_files = {}

    # ------------------------------------------------------------------ scan
    def start_scan(self, on_progress=None, on_done=None):
        with self._lock:
            if self._scan_thread is not None and self._scan_thread.is_alive():
                return
            t = threading.Thread(target=self._scan, args=(on_progress, on_done),
                                 name="library-scan", daemon=True)
            self._scan_thread = t
        t.start()

    def is_scanning(self):
        t = self._scan_thread
        return t is not None and t.is_alive()

    def _walk(self):
        found = []
        if not os.path.isdir(self.music_dir):
            return found
        for root, dirs, files in os.walk(self.music_dir):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            for name in sorted(files):
                if name.startswith("."):
                    continue
                if name.lower().endswith(self._exts):
                    found.append(os.path.join(root, name))
        return found

    def _load_index(self):
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("version") == INDEX_VERSION and isinstance(data.get("files"), dict):
                return data["files"]
        except (OSError, ValueError, AttributeError):
            pass
        return {}

    def _save_index(self, files):
        try:
            os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
            tmp = self.index_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"version": INDEX_VERSION, "files": files}, f)
            os.replace(tmp, self.index_path)
        except OSError as e:
            print(f"Library: could not save index: {e}")

    def _scan(self, on_progress, on_done):
        try:
            old = self._load_index()
            paths = self._walk()
            total = len(paths)
            new_index = {}
            tracks = []
            for i, path in enumerate(paths, 1):
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                key = [st.st_mtime, st.st_size]
                cached = old.get(path)
                if cached and cached.get("key") == key:
                    meta = cached["meta"]
                else:
                    meta = self._meta_for(path)
                new_index[path] = {"key": key, "meta": meta}
                tracks.append(self._make_track(path, meta))
                if on_progress and (i % 10 == 0 or i == total):
                    try:
                        on_progress(i, total)
                    except Exception as e:
                        print(f"Library: progress callback failed: {e}")
            if on_progress and total == 0:
                on_progress(0, 0)
            self._build(tracks)
            self._save_index(new_index)
        except Exception as e:  # never leave the UI waiting on a dead scan
            print(f"Library: scan failed: {e}")
        finally:
            if on_done:
                try:
                    on_done()
                except Exception as e:
                    print(f"Library: done callback failed: {e}")

    # -------------------------------------------------------------- metadata
    def _meta_for(self, path):
        try:
            tags = self._read_tags(path)
        except Exception as e:
            print(f"Library: tag error {path}: {e}")
            tags = {}
        stem = clean_text(os.path.splitext(os.path.basename(path))[0]) or "Unknown"
        title = clean_text(tags.get("title"))
        artist = clean_text(tags.get("artist"))
        if not title:
            if " - " in stem and not artist:
                artist, title = [p.strip() for p in stem.split(" - ", 1)]
            else:
                title = stem
        return {
            "title": title or stem,
            "artist": artist or UNKNOWN_ARTIST,
            "album": clean_text(tags.get("album")) or UNKNOWN_ALBUM,
            "duration": tags.get("duration"),
            "track_no": tags.get("track_no"),
        }

    def _read_tags(self, path):
        """Return {title, artist, album, duration, track_no}; {} if unreadable."""
        if not MUTAGEN_AVAILABLE:
            return {}
        audio = MutagenFile(path, easy=True)
        if audio is None:
            return {}
        length = getattr(getattr(audio, "info", None), "length", None)
        return {
            "title": _first(audio.get("title")),
            "artist": _first(audio.get("artist")),
            "album": _first(audio.get("album")),
            "track_no": _track_no(audio.get("tracknumber")),
            "duration": float(length) if length else None,
        }

    @staticmethod
    def _make_track(path, meta):
        return {
            "id": track_id(path), "path": path,
            "title": clean_text(meta["title"]) or "Unknown",
            "artist": clean_text(meta["artist"]) or UNKNOWN_ARTIST,
            "album": clean_text(meta["album"]) or UNKNOWN_ALBUM,
            "duration": meta.get("duration"), "track_no": meta.get("track_no"),
        }

    # ----------------------------------------------------------------- index
    def _sidecar(self, directory):
        if directory in self._art_files:
            return self._art_files[directory]
        found = None
        try:
            names = {n.lower(): n for n in os.listdir(directory)}
            for stem in SIDECAR_STEMS:
                for ext in SIDECAR_EXTS:
                    if stem + ext in names:
                        found = os.path.join(directory, names[stem + ext])
                        break
                if found:
                    break
        except OSError:
            pass
        self._art_files[directory] = found
        return found

    def _build(self, tracks):
        tracks.sort(key=lambda t: (t["title"].casefold(), t["path"]))
        by_artist, by_album = {}, {}
        for t in tracks:
            by_artist.setdefault(t["artist"], []).append(t)
            by_album.setdefault((t["album"], t["artist"]), []).append(t)

        def order(t):
            return (t["track_no"] if t["track_no"] is not None else 10 ** 6,
                    t["title"].casefold())

        for lst in by_album.values():
            lst.sort(key=order)
        self._art_files = {}
        artists = []
        for name in sorted(by_artist, key=str.casefold):
            lst = by_artist[name]
            artists.append({"name": name,
                            "album_count": len({t["album"] for t in lst}),
                            "track_count": len(lst)})
        albums = []
        for (title, artist) in sorted(by_album, key=lambda k: (k[0].casefold(), k[1].casefold())):
            lst = by_album[(title, artist)]
            art = self._sidecar(os.path.dirname(lst[0]["path"]))
            albums.append({"title": title, "artist": artist,
                           "track_count": len(lst), "art_path": art})
        idx = [((t["title"] + "\n" + t["artist"] + "\n" + t["album"]).casefold(), t)
               for t in tracks]
        with self._lock:
            self._tracks, self._artists, self._albums = tracks, artists, albums
            self._by_artist, self._by_album, self._search_idx = by_artist, by_album, idx
        with self._art_lock:
            self._art_cache.clear()
            self._art_bytes = 0

    # --------------------------------------------------------------- queries
    def get_tracks(self):
        return self._tracks

    def get_artists(self):
        return self._artists

    def get_albums(self, artist=None):
        if artist is None:
            return self._albums
        return [a for a in self._albums if a["artist"] == artist]

    def tracks_for_artist(self, name):
        lst = list(self._by_artist.get(name, []))
        lst.sort(key=lambda t: (t["album"].casefold(),
                                t["track_no"] if t["track_no"] is not None else 10 ** 6,
                                t["title"].casefold()))
        return lst

    def tracks_for_album(self, title, artist):
        return list(self._by_album.get((title, artist), []))

    def search(self, query, kind="all"):
        out = {"songs": [], "artists": [], "albums": []}
        q = (query or "").strip().casefold()
        if not q:
            return out
        if kind in ("all", "songs"):
            out["songs"] = [t for blob, t in self._search_idx if q in blob]
        if kind in ("all", "artists"):
            out["artists"] = [a for a in self._artists if q in a["name"].casefold()]
        if kind in ("all", "albums"):
            out["albums"] = [a for a in self._albums
                             if q in a["title"].casefold() or q in a["artist"].casefold()]
        return out

    # ------------------------------------------------------------------- art
    def get_art(self, track, size):
        """Square pygame Surface (cover-cropped) or None. LRU-cached; safe off the UI thread."""
        if not track or not track.get("path"):
            return None
        key = (track.get("id"), size)
        with self._art_lock:
            if key in self._art_cache:
                self._art_cache.move_to_end(key)
                return self._art_cache[key]
        surf = self._load_art(track, size)
        with self._art_lock:
            if key not in self._art_cache:
                self._art_cache[key] = surf
                self._art_bytes += self._surf_bytes(surf)
            while (self._art_bytes > ART_CACHE_BYTES
                   or len(self._art_cache) > ART_CACHE_MAX_ENTRIES) and self._art_cache:
                _k, old = self._art_cache.popitem(last=False)
                self._art_bytes -= self._surf_bytes(old)
        return surf

    @staticmethod
    def _surf_bytes(surf):
        return surf.get_width() * surf.get_height() * 4 if surf is not None else 0

    def _load_art(self, track, size):
        try:
            import pygame
            data = None
            side = self._sidecar(os.path.dirname(track["path"]))
            if side:
                with open(side, "rb") as f:
                    data = f.read()
            else:
                data = self._embedded_art(track["path"])
            if not data:
                return None
            img = pygame.image.load(io.BytesIO(data))
            w, h = img.get_size()
            s = min(w, h)
            img = img.subsurface(((w - s) // 2, (h - s) // 2, s, s))
            return pygame.transform.smoothscale(img, (size, size))
        except Exception as e:
            print(f"Library: art error {track.get('path')}: {e}")
            return None

    @staticmethod
    def _embedded_art(path):
        if not MUTAGEN_AVAILABLE:
            return None
        f = MutagenFile(path)
        if f is None:
            return None
        pics = getattr(f, "pictures", None)  # flac / ogg-flac
        if pics:
            return pics[0].data
        tags = getattr(f, "tags", None)
        if tags is None:
            return None
        if hasattr(tags, "getall"):  # id3
            apic = tags.getall("APIC")
            if apic:
                return apic[0].data
        if "covr" in tags:  # mp4/m4a
            return bytes(tags["covr"][0])
        return None


class MockMusicLibrary(MusicLibrary):
    """Small fixed library for TEST_MODE with no real music; no files needed."""

    DEMO = [
        ("Bohemian Rhapsody", "Queen", "A Night at the Opera", 354),
        ("Stairway to Heaven", "Led Zeppelin", "Led Zeppelin IV", 482),
        ("Hotel California", "Eagles", "Hotel California", 391),
        ("Imagine", "John Lennon", "Imagine", 183),
        ("Sweet Child O' Mine", "Guns N' Roses", "Appetite for Destruction", 356),
    ]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        tracks = []
        for i, (t, ar, al, d) in enumerate(self.DEMO, 1):
            p = f"/mock/{ar}/{al}/{t}.mp3"
            tracks.append({"id": track_id(p), "path": p, "title": t, "artist": ar,
                           "album": al, "duration": float(d), "track_no": i})
        self._build(tracks)

    def start_scan(self, on_progress=None, on_done=None):
        if on_progress:
            on_progress(len(self._tracks), len(self._tracks))
        if on_done:
            on_done()

    def get_art(self, track, size):
        return None

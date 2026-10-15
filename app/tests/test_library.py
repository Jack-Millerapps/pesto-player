import json
import os
import threading
import time

import pytest

from player import library as libmod
from player.library import MusicLibrary, track_id


def touch(path, data=b"not really audio"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def scan_sync(lib, timeout=5):
    done = threading.Event()
    prog = []
    lib.start_scan(on_progress=lambda d, t: prog.append((d, t)), on_done=done.set)
    assert done.wait(timeout)
    return prog


@pytest.fixture
def music(tmp_path):
    root = tmp_path / "Music"
    touch(str(root / "Ann - Zeta.mp3"))
    touch(str(root / "LOUD.MP3"))
    touch(str(root / "sub" / "x.flac"))
    touch(str(root / "sub" / "y.opus"))
    touch(str(root / "notes.txt"))
    touch(str(root / ".incoming" / "half.mp3.part"))
    touch(str(root / ".incoming" / "hidden.mp3"))
    return root


def mk(music, tmp_path):
    return MusicLibrary(str(music), index_path=str(tmp_path / "idx.json"))


def test_track_id_stable_and_path_based():
    assert track_id("/a/b.mp3") == track_id("/a/b.mp3")
    assert track_id("/a/b.mp3") != track_id("/a/c.mp3")


def test_uppercase_extension_found_and_junk_ignored(music, tmp_path):
    lib = mk(music, tmp_path)
    scan_sync(lib)
    names = sorted(os.path.basename(t["path"]) for t in lib.get_tracks())
    assert names == ["Ann - Zeta.mp3", "LOUD.MP3", "x.flac", "y.opus"]


def test_missing_tags_fall_back_to_filename(music, tmp_path):
    lib = mk(music, tmp_path)
    scan_sync(lib)
    by = {os.path.basename(t["path"]): t for t in lib.get_tracks()}
    t = by["Ann - Zeta.mp3"]
    assert t["title"] == "Zeta" and t["artist"] == "Ann"
    t = by["LOUD.MP3"]
    assert t["title"] == "LOUD" and t["artist"] == "Unknown Artist" and t["album"] == "Unknown Album"
    assert t["id"] == track_id(t["path"])


def test_scan_is_nonblocking_and_reports_progress(music, tmp_path, monkeypatch):
    gate = threading.Event()
    orig = libmod.MusicLibrary._read_tags

    def slow(self, path):
        gate.wait(2)
        return orig(self, path)

    monkeypatch.setattr(libmod.MusicLibrary, "_read_tags", slow)
    lib = mk(music, tmp_path)
    done = threading.Event()
    prog = []
    t0 = time.time()
    lib.start_scan(on_progress=lambda d, t: prog.append((d, t)), on_done=done.set)
    assert time.time() - t0 < 0.5
    assert lib.is_scanning()
    gate.set()
    assert done.wait(5)
    assert not lib.is_scanning()
    assert prog and prog[-1][0] == prog[-1][1] == 4


def test_index_cache_skips_unchanged_files(music, tmp_path, monkeypatch):
    lib = mk(music, tmp_path)
    scan_sync(lib)
    calls = []
    orig = libmod.MusicLibrary._read_tags
    monkeypatch.setattr(libmod.MusicLibrary, "_read_tags",
                        lambda self, p: calls.append(p) or orig(self, p))
    lib2 = mk(music, tmp_path)
    scan_sync(lib2)
    assert calls == []
    assert len(lib2.get_tracks()) == 4
    # changed file is re-read
    p = str(music / "LOUD.MP3")
    touch(p, b"changed content longer")
    scan_sync(lib2)
    assert calls == [p]


def test_removed_file_disappears_on_rescan(music, tmp_path):
    lib = mk(music, tmp_path)
    scan_sync(lib)
    os.remove(str(music / "LOUD.MP3"))
    scan_sync(lib)
    assert len(lib.get_tracks()) == 3


def test_corrupt_index_is_ignored(music, tmp_path):
    (tmp_path / "idx.json").write_text("{not json")
    lib = mk(music, tmp_path)
    scan_sync(lib)
    assert len(lib.get_tracks()) == 4


def test_missing_music_dir_gives_empty_library(tmp_path):
    lib = MusicLibrary(str(tmp_path / "nope"), index_path=str(tmp_path / "i.json"))
    scan_sync(lib)
    assert lib.get_tracks() == [] and lib.get_artists() == [] and lib.get_albums() == []


def _tagged(monkeypatch):
    table = {
        "a.mp3": ("Alpha", "Ann", "First", 1, 100.0),
        "b.mp3": ("bravo", "Ann", "First", 2, 100.0),
        "c.mp3": ("Charlie", "Bob", "Second", 1, 100.0),
        "d.mp3": ("Ünï Song", "Bob", "Second", 2, 100.0),
    }

    def fake(self, path):
        t, ar, al, n, d = table[os.path.basename(path)]
        return {"title": t, "artist": ar, "album": al, "track_no": n, "duration": d}

    monkeypatch.setattr(libmod.MusicLibrary, "_read_tags", fake)


@pytest.fixture
def tagged(tmp_path, monkeypatch):
    _tagged(monkeypatch)
    root = tmp_path / "M"
    for n in "abcd":
        touch(str(root / f"{n}.mp3"))
    lib = MusicLibrary(str(root), index_path=str(tmp_path / "i.json"))
    scan_sync(lib)
    return lib


def test_sorted_and_grouped(tagged):
    assert [t["title"] for t in tagged.get_tracks()] == ["Alpha", "bravo", "Charlie", "Ünï Song"]
    assert tagged.get_artists() == [
        {"name": "Ann", "album_count": 1, "track_count": 2},
        {"name": "Bob", "album_count": 1, "track_count": 2},
    ]
    albums = tagged.get_albums()
    assert [(a["title"], a["artist"], a["track_count"]) for a in albums] == [
        ("First", "Ann", 2), ("Second", "Bob", 2)]
    assert [a["title"] for a in tagged.get_albums("Bob")] == ["Second"]
    assert [t["title"] for t in tagged.tracks_for_artist("Ann")] == ["Alpha", "bravo"]
    assert [t["title"] for t in tagged.tracks_for_album("Second", "Bob")] == ["Charlie", "Ünï Song"]
    assert tagged.tracks_for_artist("Nobody") == []


def test_search_case_insensitive(tagged):
    r = tagged.search("BRAV")
    assert [t["title"] for t in r["songs"]] == ["bravo"]
    assert tagged.search("ann")["artists"][0]["name"] == "Ann"
    assert tagged.search("SECOND")["albums"][0]["title"] == "Second"
    assert [t["title"] for t in tagged.search("ünï")["songs"]] == ["Ünï Song"]
    assert tagged.search("ann", kind="songs")["artists"] == []
    assert tagged.search("")["songs"] == []
    assert set(tagged.search("zzz")) == {"songs", "artists", "albums"}


def test_art_sidecar_and_missing(tagged, tmp_path):
    import pygame
    tr = tagged.get_tracks()[0]
    assert tagged.get_art(tr, 64) is None
    cover = os.path.join(os.path.dirname(tr["path"]), "cover.jpg")
    surf = pygame.Surface((10, 20))
    surf.fill((200, 0, 0))
    pygame.image.save(surf, cover)
    scan_sync(tagged)
    tr = tagged.get_tracks()[0]
    a = tagged.get_art(tr, 64)
    assert a is not None and a.get_size() == (64, 64)
    assert tagged.get_art(tr, 64) is a  # cached
    assert tagged.get_albums()[0]["art_path"] == cover

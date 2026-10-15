"""Shared pytest setup: put app/ on sys.path, force headless SDL, mock Track fixtures."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PESTO_TEST", "1")

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import hashlib  # noqa: E402

import pytest  # noqa: E402


def make_track(title, artist="Artist", album="Album", n=None, duration=180.0, path=None):
    path = path or f"/music/{artist}/{album}/{title}.mp3"
    return {
        "id": hashlib.sha1(path.encode("utf-8")).hexdigest()[:16],
        "path": path,
        "title": title,
        "artist": artist,
        "album": album,
        "duration": duration,
        "track_no": n,
    }


@pytest.fixture
def mock_tracks():
    return [
        make_track("Alpha", "Ann", "First", 1),
        make_track("Bravo", "Ann", "First", 2),
        make_track("Charlie", "Bob", "Second", 1),
        make_track("delta", "Bob", "Second", 2),
        make_track("Echo", "Cy", "Third", None),
    ]


@pytest.fixture
def track():
    return make_track("Solo")

"""Browse screens (Library hub, Songs, Artists, Albums, Playlists, Search) with fakes."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from conftest import make_track
from ui import theme
from ui.albums import AlbumDetailScreen, AlbumsScreen
from ui.artists import ArtistDetailScreen, ArtistsScreen
from ui.library import LibraryScreen, register_library_screens
from ui.playlists import PlaylistDetailScreen, PlaylistsScreen
from ui.search import SearchScreen
from ui.songs import SongsScreen, LIST_TOP, RAIL_W


class FakeSM:
    def __init__(self):
        self.calls, self.sheets, self.toasts, self.registered = [], [], [], {}

    def push(self, name, **kw): self.calls.append(("push", name, kw))
    def pop(self): self.calls.append(("pop",)); return True
    def show(self, name, **kw): self.calls.append(("show", name, kw))
    def toast(self, msg, kind="info"): self.toasts.append(msg)
    def show_sheet(self, actions): self.sheets.append(actions)
    def register(self, name, screen, tab=None): self.registered[name] = (screen, tab)


class FakePlayer:
    def __init__(self):
        self.shuffle = False
        self.queue, self.start, self.played = [], None, 0
        self.log, self.track = [], None

    def set_queue(self, tracks, start_index=0): self.queue, self.start = list(tracks), start_index
    def play(self): self.played += 1
    def enqueue(self, t): self.log.append(("enqueue", t["id"]))
    def play_next(self, t): self.log.append(("next", t["id"]))
    def get_state(self): return {"track": self.track}


class FakeStore:
    def __init__(self): self.d = {}
    def list_names(self): return sorted(self.d)
    def load(self, n): return list(self.d.get(n, []))
    def save(self, n, tracks): self.d[n] = list(tracks)
    def delete(self, n): self.d.pop(n, None)
    def add(self, n, t): self.d.setdefault(n, []).append(t)


class FakeLib:
    def __init__(self, tracks):
        self.tracks = sorted(tracks, key=lambda t: t["title"].casefold())

    def get_tracks(self): return list(self.tracks)
    def get_art(self, track, size): return None

    def get_artists(self):
        out = {}
        for t in self.tracks:
            a = out.setdefault(t["artist"], {"albums": set(), "n": 0})
            a["albums"].add(t["album"]); a["n"] += 1
        return [{"name": k, "album_count": len(v["albums"]), "track_count": v["n"]}
                for k, v in sorted(out.items())]

    def get_albums(self, artist=None):
        out = {}
        for t in self.tracks:
            if artist and t["artist"] != artist:
                continue
            k = (t["album"], t["artist"])
            out[k] = out.get(k, 0) + 1
        return [{"title": k[0], "artist": k[1], "track_count": n, "art_path": None}
                for k, n in sorted(out.items())]

    def tracks_for_artist(self, name): return [t for t in self.tracks if t["artist"] == name]
    def tracks_for_album(self, title, artist):
        return [t for t in self.tracks if t["album"] == title and t["artist"] == artist]

    def search(self, query, kind="all"):
        q = query.casefold()
        songs = [t for t in self.tracks if q in t["title"].casefold()]
        arts = [a for a in self.get_artists() if q in a["name"].casefold()]
        albs = [a for a in self.get_albums() if q in a["title"].casefold()]
        return {"songs": songs if kind in ("all", "songs") else [],
                "artists": arts if kind in ("all", "artists") else [],
                "albums": albs if kind in ("all", "albums") else []}


@pytest.fixture(scope="module", autouse=True)
def _pg():
    pygame.init()
    yield


@pytest.fixture
def env(mock_tracks):
    return FakeSM(), FakePlayer(), FakeLib(mock_tracks), FakeStore()


def make(cls, env):
    sm, pl, lib, st = env
    return cls(sm, pl, lib, st)


def surface():
    return pygame.Surface((theme.SCREEN_W, theme.SCREEN_H))


def tap(screen, pos):
    screen.handle_touch(pos, "down")
    screen.handle_touch(pos, "up")


def row_pos(row, top=LIST_TOP, h=theme.ROW_H, x=100):
    return (x, top + row * h + h // 2)


# ---------------------------------------------------------------- Songs
def test_songs_tap_sets_queue_and_plays(env):
    s = make(SongsScreen, env)
    sm, pl, lib, st = env
    tap(s, row_pos(2))
    assert [t["id"] for t in pl.queue] == [t["id"] for t in lib.tracks]
    assert pl.start == 2 and pl.played == 1


def test_songs_scroll_then_release_does_not_play(env):
    sm, pl, lib, st = env
    lib.tracks = [make_track(f"Song {i:03d}") for i in range(60)]
    s = make(SongsScreen, env)
    s.handle_touch((100, 300), "down")
    s.handle_touch((100, 250), "move")
    s.handle_touch((100, 150), "move")
    s.handle_touch((100, 150), "up")
    assert pl.played == 0 and s.list.scroll > 0


def test_songs_alphabet_rail_jumps(env):
    sm, pl, lib, st = env
    lib.tracks = [make_track(f"{c}{i}") for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for i in range(3)]
    s = make(SongsScreen, env)
    assert s.index_for_letter("A") == 0
    assert lib.tracks[s.index_for_letter("M")]["title"].startswith("M")
    x, y = theme.SCREEN_W - RAIL_W // 2, s.rail.y + s.rail.h // 2
    s.handle_touch((x, y), "down")
    s.handle_touch((x, y), "up")
    assert s.list.scroll > 0 and pl.played == 0


def test_songs_long_press_sheet_actions(env):
    sm, pl, lib, st = env
    s = make(SongsScreen, env)
    s._on_long(lib.tracks[1], 1)
    assert [a[0] for a in sm.sheets[-1]] == ["Play next", "Add to queue", "Add to playlist"]
    sm.sheets[-1][0][1]()
    sm.sheets[-1][1][1]()
    assert pl.log == [("next", lib.tracks[1]["id"]), ("enqueue", lib.tracks[1]["id"])]


def test_songs_real_long_press_opens_sheet(env):
    sm, pl, lib, st = env
    s = make(SongsScreen, env)
    t = [0.0]
    s.list.clock = lambda: t[0]
    s.handle_touch(row_pos(1), "down")
    t[0] = 0.6
    s.update(0.6)
    s.handle_touch(row_pos(1), "up")
    assert len(sm.sheets) == 1 and pl.played == 0


def test_add_to_playlist_creates_and_appends(env):
    sm, pl, lib, st = env
    s = make(SongsScreen, env)
    s._on_long(lib.tracks[0], 0)
    dict(sm.sheets[-1])["Add to playlist"]()
    dict(sm.sheets[-1])["New playlist"]()
    assert st.d["Playlist 1"] == [lib.tracks[0]]
    s._on_long(lib.tracks[1], 1)
    dict(sm.sheets[-1])["Add to playlist"]()
    dict(sm.sheets[-1])["Playlist 1"]()
    assert len(st.d["Playlist 1"]) == 2


def test_songs_draw_and_current_marker(env):
    sm, pl, lib, st = env
    pl.track = lib.tracks[0]
    s = make(SongsScreen, env)
    s.update(0.3)
    assert s.current_id == lib.tracks[0]["id"]
    s.draw(surface())


def test_missing_tags_and_long_title_draw(env):
    sm, pl, lib, st = env
    lib.tracks = [{"id": "x", "path": "/m/some_file.mp3", "title": "", "artist": "", "album": "",
                   "duration": None, "track_no": None},
                  {"id": "y", "path": "/m/y.mp3", "title": "é中" * 100, "artist": "A" * 200,
                   "album": "B", "duration": 1.0, "track_no": 1}]
    s = make(SongsScreen, env)
    s.draw(surface())


# --------------------------------------------------------------- empties
@pytest.mark.parametrize("cls", [SongsScreen, ArtistsScreen, AlbumsScreen])
def test_empty_states_have_add_music(env, cls):
    sm, pl, lib, st = env
    lib.tracks = []
    s = make(cls, env)
    s.draw(surface())
    tap(s, s.empty.button.rect.center)
    assert sm.calls[-1] == ("push", "add_music", {})


def test_playlists_search_hub_empty_draw(env):
    sm, pl, lib, st = env
    lib.tracks = []
    for cls in (PlaylistsScreen, SearchScreen, LibraryScreen):
        s = make(cls, env)
        s.on_enter()
        s.draw(surface())


# ------------------------------------------------------- artists / albums
def test_artist_flow_and_detail_play_shuffle(env):
    sm, pl, lib, st = env
    s = make(ArtistsScreen, env)
    tap(s, row_pos(1))
    assert sm.calls[-1] == ("push", "artist_detail", {"artist_name": "Bob"})
    d = make(ArtistDetailScreen, env)
    d.on_enter(artist_name="Ann")
    d.draw(surface())
    d.btn_play.on_click()
    assert [t["artist"] for t in pl.queue] == ["Ann", "Ann"] and pl.start == 0 and pl.shuffle is False
    d.btn_shuffle.on_click()
    assert pl.shuffle is True and pl.played == 2
    tap(d, d.btn_shuffle.rect.center)
    assert pl.played == 3


def test_albums_grid_tap_columns_and_detail(env):
    sm, pl, lib, st = env
    s = make(AlbumsScreen, env)
    s.draw(surface())
    tap(s, (240, LIST_TOP + 60))
    assert sm.calls[-1][:2] == ("push", "album_detail") and sm.calls[-1][2]["title"] == "Second"
    tap(s, (40, LIST_TOP + 60))
    assert sm.calls[-1][2]["title"] == "First"
    d = make(AlbumDetailScreen, env)
    d.on_enter(title="First", artist="Ann")
    d.draw(surface())
    assert len(d.tracks) == 2
    d.btn_play.on_click()
    assert pl.played == 1


# -------------------------------------------------------------- playlists
def test_playlists_create_open_delete_remove(env):
    sm, pl, lib, st = env
    s = make(PlaylistsScreen, env)
    s.btn_new.on_click()
    assert st.list_names() == ["Playlist 1"] and s.names == ["Playlist 1"]
    st.save("Playlist 1", lib.tracks[:3])
    s.reload(); s.draw(surface())
    tap(s, row_pos(0))
    assert sm.calls[-1] == ("push", "playlist_detail", {"playlist_name": "Playlist 1"})
    d = make(PlaylistDetailScreen, env)
    d.on_enter(playlist_name="Playlist 1")
    d.draw(surface())
    d.remove(0)
    assert len(st.load("Playlist 1")) == 2
    s._on_long("Playlist 1", 0)
    sm.sheets[-1][0][1]()
    assert st.list_names() == []


# ----------------------------------------------------------------- search
def test_search_filters_and_plays(env):
    sm, pl, lib, st = env
    s = make(SearchScreen, env)
    for ch in "al":
        s.on_key(ch)
    assert s.query == "al"
    songs = [r for r in s.rows if r["kind"] == "song"]
    assert songs and all("al" in r["track"]["title"].casefold() for r in songs)
    s.draw(surface())
    s.on_key("\b")
    assert s.query == "a"
    s.on_key(" ")
    assert s.query == "a "
    s.query = ""
    s.on_key("c")
    s.set_kind("songs")
    assert all(r["kind"] != "header" for r in s.rows)
    s._on_tap(s.rows[0], 0)
    assert pl.played == 1 and pl.start == 0


def test_search_artist_album_and_no_results(env):
    sm, pl, lib, st = env
    s = make(SearchScreen, env)
    s.query = "ann"; s.run_search()
    art = [r for r in s.rows if r["kind"] == "artist"]
    s._on_tap(art[0], 0)
    assert sm.calls[-1] == ("push", "artist_detail", {"artist_name": "Ann"})
    s.query = "zzzz"; s.run_search()
    assert s.rows == []
    s.draw(surface())


def test_search_keyboard_close_resizes_list(env):
    s = make(SearchScreen, env)
    h = s.list.rect.h
    s.close_keyboard()
    assert s.list.rect.h > h and s.list.rect.bottom <= theme.CONTENT_BOTTOM_MINI


# -------------------------------------------------------------------- hub
def test_hub_rows_push_screens(env):
    sm, pl, lib, st = env
    h = make(LibraryScreen, env)
    h.on_enter()
    h.draw(surface())
    expected = ["songs", "artists", "albums", "playlists", "search", "add_music"]
    for i, name in enumerate(expected):
        tap(h, row_pos(i, h=48))
        assert sm.calls[-1] == ("push", name, {})


def test_no_spotify_left():
    import inspect
    import ui.library as m
    assert "spotify" not in inspect.getsource(m).lower()


def test_register_helper(env):
    sm, pl, lib, st = env
    register_library_screens(sm, pl, lib, st)
    assert sm.registered["library"][1] == "library"
    for n in ("songs", "artists", "albums", "playlists", "search",
              "artist_detail", "album_detail", "playlist_detail"):
        assert n in sm.registered


def test_back_button_pops(env):
    s = make(SongsScreen, env)
    tap(s, s.back_button.rect.center)
    assert env[0].calls[-1] == ("pop",)

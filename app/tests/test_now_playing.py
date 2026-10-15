"""Tests for Builder B's playback UI: Now Playing, Queue, MiniPlayer, VolumeHUD.

Uses local fakes (no dependency on A's widget behavior or D's real player).
"""
import pygame
import pytest

from conftest import make_track
from ui import theme
from ui.now_playing import NowPlayingScreen
from ui.queue import QueueScreen
from ui.mini_player import MiniPlayer
from ui.volume_hud import VolumeHUD
from ui.widgets import Marquee


@pytest.fixture(scope="module", autouse=True)
def _pg():
    pygame.init()
    pygame.display.set_mode((320, 480))
    yield


class FakeSM:
    def __init__(self):
        self.shown, self.toasts, self.sheets = [], [], []
        self.mini_player = None

    def show(self, name, **kw): self.shown.append(name)
    def push(self, name, **kw): self.shown.append(name)
    def toast(self, msg, kind="info"): self.toasts.append((msg, kind))
    def show_sheet(self, actions): self.sheets.append(actions)


class FakeAudio:
    def __init__(self, tracks=(), index=-1, playing=False):
        self.shuffle = False
        self.repeat = "off"
        self.queue = list(tracks)
        self.index = index
        self.playing = playing
        self.position = 0.0
        self.volume = 50
        self.calls = []

    def get_state(self):
        t = self.queue[self.index] if 0 <= self.index < len(self.queue) else None
        return {"track": t, "playing": self.playing, "position": self.position,
                "duration": (t or {}).get("duration") or 0.0, "volume": self.volume,
                "shuffle": self.shuffle, "repeat": self.repeat, "queue_index": self.index}

    def get_queue(self): return list(self.queue)
    def set_queue(self, tracks, start_index=0):
        self.queue = list(tracks); self.index = start_index; self.calls.append(("set_queue", start_index))
    def remove_from_queue(self, i):
        self.calls.append(("remove", i)); del self.queue[i]
    def move_in_queue(self, s, d): self.calls.append(("move", s, d))
    def toggle(self): self.calls.append(("toggle",))
    def next(self): self.calls.append(("next",))
    def prev(self): self.calls.append(("prev",))
    def seek(self, f): self.calls.append(("seek", f))
    def set_volume(self, v): self.calls.append(("vol", v))


class FakeLib:
    def __init__(self): self.art_calls = 0
    def get_art(self, track, size):
        self.art_calls += 1
        s = pygame.Surface((size, size)); s.fill((200, 10, 10)); return s


def mk(tracks=None, playing=True):
    tracks = tracks if tracks is not None else [make_track("Alpha"), make_track("Bravo")]
    audio = FakeAudio(tracks, 0 if tracks else -1, playing)
    sm = FakeSM()
    return sm, audio, FakeLib()


def rects_of(np):
    return [np.shuffle_rect, np.prev_rect, np.play_rect, np.next_rect, np.repeat_rect,
            np.art_rect, np.seek_rect, np.title_rect]


def test_layout_within_screen_and_above_tab_bar():
    sm, audio, lib = mk()
    np = NowPlayingScreen(sm, audio, lib)
    assert np.has_mini_player is False
    for r in rects_of(np):
        assert r.top >= 0 and r.bottom <= theme.TAB_Y, r
        assert r.left >= 0 and r.right <= 320, r
    for r in (np.shuffle_rect, np.prev_rect, np.play_rect, np.next_rect, np.repeat_rect, np.seek_rect):
        assert r.h >= theme.MIN_TOUCH and r.w >= theme.MIN_TOUCH, r
    assert np.art_rect.top >= theme.STATUS_H


def test_seek_commits_on_release_only():
    sm, audio, lib = mk()
    np = NowPlayingScreen(sm, audio, lib)
    y = np.seek_rect.centery
    np.handle_touch((np.seek_rect.centerx, y), "down")
    np.handle_touch((np.seek_rect.right - 1, y), "move")
    assert not [c for c in audio.calls if c[0] == "seek"]
    assert np.seek_dragging
    np.handle_touch((np.seek_rect.centerx, y), "up")
    seeks = [c for c in audio.calls if c[0] == "seek"]
    assert len(seeks) == 1 and 0.4 < seeks[0][1] < 0.6


def test_seek_cancel_does_not_commit():
    sm, audio, lib = mk()
    np = NowPlayingScreen(sm, audio, lib)
    np.handle_touch(np.seek_rect.center, "down")
    np.handle_touch(np.seek_rect.center, "cancel")
    assert not [c for c in audio.calls if c[0] == "seek"]
    assert not np.seek_dragging


def test_buttons_fire_on_release_inside_and_cancel_on_drag_out():
    sm, audio, lib = mk()
    np = NowPlayingScreen(sm, audio, lib)
    np.handle_touch(np.play_rect.center, "down")
    assert ("toggle",) not in audio.calls
    np.handle_touch(np.play_rect.center, "up")
    assert ("toggle",) in audio.calls
    audio.calls.clear()
    np.handle_touch(np.next_rect.center, "down")
    np.handle_touch(np.prev_rect.center, "up")   # released elsewhere
    assert audio.calls == []
    np.handle_touch(np.prev_rect.center, "down")
    np.handle_touch(np.prev_rect.center, "up")
    assert audio.calls == [("prev",)]


def test_shuffle_and_repeat_cycle():
    sm, audio, lib = mk()
    np = NowPlayingScreen(sm, audio, lib)
    for _ in range(2):
        pass
    np.handle_touch(np.shuffle_rect.center, "down"); np.handle_touch(np.shuffle_rect.center, "up")
    assert audio.shuffle is True
    seen = []
    for _ in range(3):
        np.handle_touch(np.repeat_rect.center, "down"); np.handle_touch(np.repeat_rect.center, "up")
        seen.append(audio.repeat)
    assert seen == ["all", "one", "off"]


def test_time_label_rerenders_only_when_second_changes():
    sm, audio, lib = mk()
    np = NowPlayingScreen(sm, audio, lib)
    np.update(0.3)
    base = np.time_renders
    audio.position = 0.4
    np.update(0.3)
    audio.position = 0.8
    np.update(0.3)
    assert np.time_renders == base
    audio.position = 1.2
    np.update(0.3)
    assert np.time_renders == base + 1


def test_state_poll_rate_limited():
    sm, audio, lib = mk()
    calls = {"n": 0}
    orig = audio.get_state
    def counting():
        calls["n"] += 1
        return orig()
    audio.get_state = counting
    np = NowPlayingScreen(sm, audio, lib)
    calls["n"] = 0
    for _ in range(30):          # 30 frames at 30 fps = 1 s
        np.update(1 / 30)
    assert calls["n"] <= 5


def test_empty_state_renders_without_crash():
    sm, audio, lib = mk(tracks=[])
    np = NowPlayingScreen(sm, audio, lib)
    np.on_enter()
    np.update(0.5)
    surf = pygame.Surface((320, 480))
    np.draw(surf)
    assert np.title_text == "Nothing playing"
    np.handle_touch(np.play_rect.center, "down"); np.handle_touch(np.play_rect.center, "up")
    assert ("toggle",) not in audio.calls


def test_long_title_uses_marquee_and_missing_tags_fall_back():
    long = make_track("T" * 200)
    sm, audio, lib = mk([long])
    np = NowPlayingScreen(sm, audio, lib)
    np.update(0.5)
    assert isinstance(np.title_marquee, Marquee)
    assert np.title_marquee.text == "T" * 200
    np.draw(pygame.Surface((320, 480)))
    bare = {"id": "x", "path": "/m/some_file.mp3", "title": None, "artist": None, "album": None}
    sm, audio, lib = mk([bare])
    np = NowPlayingScreen(sm, audio, lib)
    np.update(0.5)
    assert np.title_text == "some_file"
    np.draw(pygame.Surface((320, 480)))


def test_art_loaded_async_and_cached():
    import time
    sm, audio, lib = mk()
    np = NowPlayingScreen(sm, audio, lib)
    np.update(0.5)
    for _ in range(100):
        np.update(0.05)
        if np.art_surface is not None:
            break
        time.sleep(0.01)
    assert np.art_surface is not None
    n = lib.art_calls
    np.on_enter(); np.update(0.5)
    assert lib.art_calls == n   # LRU hit, no second fetch
    np.draw(pygame.Surface((320, 480)))


def test_non_ascii_title_draws():
    sm, audio, lib = mk([make_track("Ünïcødé 歌 ☃")])
    np = NowPlayingScreen(sm, audio, lib)
    np.update(0.5); np.draw(pygame.Surface((320, 480)))


# --- Queue -----------------------------------------------------------------
def test_queue_empty_state_and_draw():
    sm, audio, lib = mk(tracks=[])
    q = QueueScreen(sm, audio, lib)
    q.on_enter(); q.update(0.5)
    q.draw(pygame.Surface((320, 480)))
    assert q.is_empty()


def test_queue_tap_plays_that_index_and_actions():
    tracks = [make_track(n) for n in "ABCD"]
    sm, audio, lib = mk(tracks)
    q = QueueScreen(sm, audio, lib)
    q.on_enter()
    q.on_tap(tracks[2], 2)
    assert ("set_queue", 2) in audio.calls
    q.on_long_press(tracks[1], 1)
    labels = [a[0] for a in sm.sheets[-1]]
    assert "Remove" in labels and "Move up" in labels and "Move down" in labels
    dict((a[0], a[1]) for a in sm.sheets[-1])["Move up"]()
    assert ("move", 1, 0) in audio.calls
    q.on_remove(1)
    assert ("remove", 1) in audio.calls


def test_queue_clear_and_save(monkeypatch):
    tracks = [make_track(n) for n in "AB"]
    sm, audio, lib = mk(tracks)
    saved = {}
    class Store:
        def save(self, name, tr): saved[name] = list(tr)
    q = QueueScreen(sm, audio, lib, playlist_store=Store())
    q.on_enter()
    q.save_as_playlist()
    assert len(saved) == 1 and len(list(saved.values())[0]) == 2
    q.clear()
    assert ("set_queue", 0) in audio.calls and audio.queue == []


def test_queue_layout_clears_mini_player():
    sm, audio, lib = mk()
    q = QueueScreen(sm, audio, lib)
    assert q.has_mini_player is True
    assert q.list.rect.bottom <= theme.MINI_Y
    for r in (q.save_rect, q.clear_rect):
        assert r.h >= theme.MIN_TOUCH and r.bottom <= q.list.rect.top + 2


# --- MiniPlayer ------------------------------------------------------------
def test_mini_player_geometry_tap_and_play():
    sm, audio, lib = mk()
    mp = MiniPlayer(sm, audio, lib)
    assert mp.rect == pygame.Rect(0, theme.MINI_Y, 320, theme.MINI_H)
    assert mp.play_rect.h >= theme.MIN_TOUCH or mp.play_rect.h == theme.MINI_H
    assert mp.play_rect.right <= 320 and mp.play_rect.bottom <= theme.TAB_Y
    mp.update(0.5)
    mp.draw(pygame.Surface((320, 480)))
    assert mp.handle_touch((10, 10), "down") is False      # outside
    mp.handle_touch(mp.play_rect.center, "down"); mp.handle_touch(mp.play_rect.center, "up")
    assert ("toggle",) in audio.calls and sm.shown == []
    mp.handle_touch((40, mp.rect.centery), "down"); mp.handle_touch((40, mp.rect.centery), "up")
    assert sm.shown == ["now_playing"]


def test_mini_player_no_track_draws():
    sm, audio, lib = mk(tracks=[])
    mp = MiniPlayer(sm, audio, lib)
    mp.update(0.5); mp.draw(pygame.Surface((320, 480)))


# --- VolumeHUD -------------------------------------------------------------
def test_volume_hud_lifecycle():
    h = VolumeHUD()
    surf = pygame.Surface((320, 480))
    assert not h.visible
    h.show(70)
    assert h.visible and h.volume == 70
    h.draw(surf)
    h.update(1.0)
    assert h.visible
    h.update(0.3)
    assert not h.visible
    h.show(500); assert h.volume == 100
    h.show(-5); assert h.volume == 0


# --- review fixes (real ScreenManager / ScrollList) --------------------------
def test_volume_hud_active_and_no_perpetual_dirty_with_real_manager():
    from ui.screen_manager import ScreenManager
    surf = pygame.Surface((320, 480))
    sm = ScreenManager(surf)
    _, audio, lib = mk()
    np_ = NowPlayingScreen(sm, audio, lib)
    sm.register("now_playing", np_, tab="now_playing")
    hud = VolumeHUD()
    sm.add_overlay(hud)
    sm.show("now_playing")
    sm.draw()
    assert hud.active is False
    hud.show(60)
    assert hud.active is True
    assert sm.draw()
    sm.update(2.0)
    assert hud.active is False
    sm.draw()                       # repaint that erases the HUD
    assert sm.draw() == []
    assert sm.draw() == []
    assert hud.dirty is False


def test_volume_hud_below_toast_band():
    h = VolumeHUD()
    assert h.rect.top >= theme.STATUS_H + 6 + 36


def test_title_centered_when_short_and_bubble_clear_of_album_line():
    sm, audio, lib = mk([make_track("Hi")])
    np_ = NowPlayingScreen(sm, audio, lib)
    assert abs(np_.title_marquee.rect.centerx - np_.title_rect.centerx) <= 1
    sm, audio, lib = mk(tracks=[])
    np_ = NowPlayingScreen(sm, audio, lib)
    assert abs(np_.title_marquee.rect.centerx - np_.title_rect.centerx) <= 1
    sm, audio, lib = mk([make_track("Hi")])
    np_ = NowPlayingScreen(sm, audio, lib)
    np_.handle_touch(np_.seek_rect.center, "down")
    np_.draw(pygame.Surface((320, 480)))
    assert not np_.bubble_rect.colliderect(np_.album_rect)
    assert not np_.bubble_rect.colliderect(np_.artist_rect)


def test_scrolling_title_marks_sub_rect_only_when_manager_supports_it():
    sm, audio, lib = mk([make_track("T" * 200)])
    np_ = NowPlayingScreen(sm, audio, lib)
    np_.draw(pygame.Surface((320, 480)))
    assert np_.dirty is False
    for _ in range(60):
        np_.update(1 / 30)
    assert np_.dirty is True               # fallback: no dirty-rect support in FakeSM
    np_.draw(pygame.Surface((320, 480)))
    sm.supports_dirty_rects = True
    np_.dirty_rects = []
    for _ in range(60):
        np_.update(1 / 30)
    assert np_.dirty is False
    assert np_.dirty_rects and all(r.colliderect(np_.title_rect) and np_.title_rect.contains(r)
                                   for r in np_.dirty_rects)


def test_queue_real_scrolllist_tap_plays_and_scroll_does_not():
    from ui.screen_manager import ScreenManager
    tracks = [make_track("T%d" % i) for i in range(12)]
    sm = ScreenManager(pygame.Surface((320, 480)))
    _, audio, lib = mk(tracks)
    q = QueueScreen(sm, audio, lib)
    sm.register("queue", q, tab="queue")
    sm.show("queue")
    sm.draw()
    p = (100, q.list_rect.top + 56 + 20)       # row 1
    sm.handle_touch(p, "down"); sm.handle_touch(p, "up")
    assert ("set_queue", 1) in audio.calls
    audio.calls.clear()
    sm.handle_touch((100, 300), "down")
    sm.handle_touch((100, 200), "move")
    sm.handle_touch((100, 150), "up")
    assert not [c for c in audio.calls if c[0] == "set_queue"]


def test_scrolling_title_uses_real_manager_sub_rects():
    from ui.screen_manager import ScreenManager
    sm = ScreenManager(pygame.Surface((320, 480)))
    _, audio, lib = mk([make_track("T" * 200)])
    np_ = NowPlayingScreen(sm, audio, lib)
    sm.register("now_playing", np_, tab="now_playing")
    sm.show("now_playing")
    sm.draw()
    got = []
    for _ in range(90):
        sm.update(1 / 30)
        got += sm.draw()
    assert got
    tail = got[3:]       # first frames may carry a legitimate full repaint (async art arrives)
    assert len(tail) > 20
    assert all(np_.title_rect.contains(r) for r in tail)

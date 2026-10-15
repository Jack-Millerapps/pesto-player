import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
import pytest

from ui import text_cache, theme
from ui.keyboard import Keyboard
from ui.widgets import Button, Marquee, ScrollList, Slider, TabBar


@pytest.fixture(scope="module", autouse=True)
def _pg():
    pygame.init()
    pygame.display.set_mode((320, 480))
    yield


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


def make_list(n=100, **kw):
    calls = []
    taps = []
    longs = []

    def draw_row(surface, rect, item, index, state):
        calls.append(index)

    lst = ScrollList((0, 24, 320, 350), 56, draw_row,
                     on_tap=lambda it, i: taps.append((it, i)),
                     on_long_press=lambda it, i: longs.append((it, i)),
                     items=list(range(n)), **kw)
    clock = Clock()
    lst.clock = clock
    return lst, calls, taps, longs, clock


# ---- ScrollList ----
def test_only_visible_rows_drawn():
    lst, calls, *_ = make_list(1000)
    surf = pygame.Surface((320, 480))
    lst.draw(surf)
    assert 0 < len(calls) <= 350 // 56 + 2


def test_tap_fires_with_item_and_index():
    lst, calls, taps, longs, clock = make_list()
    lst.handle_touch((50, 24 + 56 * 2 + 5), "down")
    clock.advance(0.1)
    lst.handle_touch((52, 24 + 56 * 2 + 6), "up")
    assert taps == [(2, 2)]


def test_drag_over_10px_does_not_tap_and_scrolls():
    lst, calls, taps, longs, clock = make_list()
    lst.handle_touch((50, 200), "down")
    clock.advance(0.05)
    lst.handle_touch((50, 180), "move")
    clock.advance(0.05)
    lst.handle_touch((50, 150), "up")
    assert taps == []
    assert lst.scroll > 0


def test_slow_press_is_not_tap():
    lst, calls, taps, longs, clock = make_list(on_long_press=None) if False else make_list()
    lst.on_long_press = None
    lst.handle_touch((50, 100), "down")
    clock.advance(0.4)
    lst.handle_touch((50, 100), "up")
    assert taps == []


def test_long_press_fires_at_500ms_and_suppresses_tap():
    lst, calls, taps, longs, clock = make_list()
    lst.handle_touch((50, 24 + 56 + 5), "down")
    clock.advance(0.3)
    lst.update(0.3)
    assert longs == []
    clock.advance(0.25)
    lst.update(0.25)
    assert longs == [(1, 1)]
    lst.handle_touch((50, 24 + 56 + 5), "up")
    assert taps == []


def test_flick_decays_and_new_down_stops():
    lst, calls, taps, longs, clock = make_list()
    lst.handle_touch((50, 300), "down")
    for y in (280, 250, 210, 160):
        clock.advance(0.016)
        lst.handle_touch((50, y), "move")
    lst.handle_touch((50, 150), "up")
    assert taps == []
    s0 = lst.scroll
    moved = []
    for _ in range(300):
        clock.advance(0.016)
        lst.update(0.016)
        moved.append(lst.scroll)
    assert moved[0] > s0
    assert moved[-1] == moved[-2]  # stopped
    # new flick then stop on touch
    lst.scroll = 0
    lst.handle_touch((50, 300), "down")
    for y in (280, 250, 210, 160):
        clock.advance(0.016)
        lst.handle_touch((50, y), "move")
    lst.handle_touch((50, 150), "up")
    lst.update(0.016)
    lst.handle_touch((50, 100), "down")
    before = lst.scroll
    lst.update(0.1)
    assert lst.scroll == before
    lst.handle_touch((50, 100), "cancel")


def test_scroll_clamped():
    lst, *_ = make_list(5)
    assert lst.scroll == 0
    lst.handle_touch((50, 200), "down")
    lst.handle_touch((50, 100), "move")
    lst.handle_touch((50, 100), "up")
    assert lst.scroll == 0


def test_scroll_to_index():
    lst, *_ = make_list(100)
    lst.scroll_to_index(50)
    assert lst.scroll == 50 * 56
    lst.scroll_to_index(9999)
    assert lst.scroll == 100 * 56 - 350


def test_empty_list_draws():
    lst, calls, *_ = make_list(0)
    lst.draw(pygame.Surface((320, 480)))
    assert calls == []


# ---- Button ----
def test_button_click_and_drag_out_cancel():
    hits = []
    b = Button((10, 10, 100, 50), "Go", on_click=lambda: hits.append(1))
    b.handle_touch((20, 20), "down")
    assert b.pressed
    b.handle_touch((20, 20), "up")
    assert hits == [1] and not b.pressed
    b.handle_touch((20, 20), "down")
    b.handle_touch((300, 300), "move")
    assert not b.pressed
    b.handle_touch((300, 300), "up")
    assert hits == [1]
    b.handle_touch((20, 20), "down")
    b.handle_touch((20, 20), "cancel")
    assert not b.pressed
    b.handle_touch((20, 20), "up")
    assert hits == [1]


def test_disabled_button_ignores():
    hits = []
    b = Button((0, 0, 50, 50), "x", on_click=lambda: hits.append(1), enabled=False)
    b.handle_touch((5, 5), "down")
    b.handle_touch((5, 5), "up")
    assert hits == []


# ---- Slider ----
def test_slider_commits_on_release_only():
    changes, commits = [], []
    s = Slider((20, 100, 200, 44), 0.0, on_change=changes.append, on_commit=commits.append)
    s.handle_touch((120, 120), "down")
    s.handle_touch((170, 120), "move")
    assert commits == [] and changes
    s.handle_touch((170, 120), "up")
    assert len(commits) == 1 and 0.0 <= commits[0] <= 1.0
    assert abs(commits[0] - 0.75) < 0.1


def test_slider_hit_zone_44px_and_cancel():
    commits = []
    s = Slider((20, 100, 200, 8), 0.5, on_commit=commits.append)
    assert s.handle_touch((50, 100 + 4 + 20), "down")  # within 44 px zone
    s.handle_touch((50, 124), "cancel")
    assert commits == [] and not s.dragging


# ---- TabBar ----
def test_tabbar_select():
    sel = []
    t = TabBar((0, 424, 320, 56), [("a", "A"), ("b", "B"), ("c", "C"), ("d", "D")], sel.append)
    t.handle_touch((100, 440), "down")
    t.handle_touch((100, 440), "up")
    assert sel == ["b"]
    t.set_active("b")
    assert t.active == "b"
    t.draw(pygame.Surface((320, 480)))


# ---- Marquee ----
def test_marquee_scrolls_only_when_overflowing():
    m = Marquee((0, 0, 100, 24), "short", 18)
    for _ in range(100):
        m.update(0.1)
    assert m.offset == 0
    m2 = Marquee((0, 0, 100, 24), "A very long track title that overflows" * 3, 18)
    for _ in range(40):
        m2.update(0.1)
    assert m2.offset > 0
    m2.set_text("x" * 200)
    assert m2.offset == 0
    m2.draw(pygame.Surface((320, 480)))


# ---- text_cache ----
def test_text_cache_same_surface():
    a = text_cache.render("hello", 16, (255, 255, 255))
    b = text_cache.render("hello", 16, (255, 255, 255))
    assert a is b
    assert text_cache.render("hello", 16, (1, 2, 3)) is not a
    assert text_cache.get_font(16) is text_cache.get_font(16)


def test_text_cache_lru_bounded():
    for i in range(text_cache.TEXT_CACHE_MAX + 50):
        text_cache.render("t%d" % i, 12, (9, 9, 9))
    assert len(text_cache._text) <= text_cache.TEXT_CACHE_MAX


def test_ellipsize_respects_width():
    long = "This is a very long title " * 8
    for w in (30, 80, 200):
        out = text_cache.ellipsize(long, 16, w)
        assert text_cache.text_width(out, 16) <= w
        assert out.endswith("...") or out == ""
    assert text_cache.ellipsize("hi", 16, 200) == "hi"
    assert text_cache.ellipsize("anything", 16, 0) == ""
    assert text_cache.ellipsize("こんにちは" * 20, 16, 100) is not None


# ---- Keyboard ----
def test_keyboard_keys_and_layout():
    keys, enters, closes = [], [], []
    k = Keyboard((0, 230, 320, 194), keys.append, lambda: enters.append(1), lambda: closes.append(1))
    surf = pygame.Surface((320, 480))
    k.draw(surf)
    # tap every key center; find q
    found = {}
    for label, r in k.key_rects():
        assert k.rect.contains(r)
        assert r.height >= 36
        found[label] = r
    assert "q" in found and "ENTER" in found and "BKSP" in found and "CLOSE" in found
    for lab in ("q", "BKSP", "ENTER", "CLOSE"):
        c = found[lab].center
        k.handle_touch(c, "down")
        k.handle_touch(c, "up")
    assert keys == ["q", "\b"]
    assert enters == [1] and closes == [1]

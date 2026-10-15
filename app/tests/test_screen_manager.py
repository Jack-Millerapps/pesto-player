import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
import pytest

from ui import theme
from ui.screen_manager import Screen, ScreenManager


@pytest.fixture(scope="module", autouse=True)
def _pg():
    pygame.init()
    pygame.display.set_mode((320, 480))
    yield


class Rec(Screen):
    def __init__(self, sm, has_mini=True):
        super().__init__(sm)
        self.has_mini_player = has_mini
        self.log = []
        self.touches = []
        self.draws = 0

    def on_enter(self, **kw):
        self.log.append(("enter", kw))

    def on_leave(self):
        self.log.append(("leave",))

    def handle_touch(self, pos, kind):
        self.touches.append((pos, kind))
        return True

    def draw(self, surface):
        self.draws += 1


def make():
    surf = pygame.Surface((320, 480))
    sm = ScreenManager(surf)
    scr = {n: Rec(sm, n != "now_playing") for n in
           ("now_playing", "library", "queue", "settings", "songs", "artists", "albums")}
    sm.register("now_playing", scr["now_playing"], tab="now_playing")
    sm.register("library", scr["library"], tab="library")
    sm.register("queue", scr["queue"], tab="queue")
    sm.register("settings", scr["settings"], tab="settings")
    for n in ("songs", "artists", "albums"):
        sm.register(n, scr[n], tab="library")
    return sm, scr, surf


def tab_center(i):
    return (i * 80 + 40, theme.TAB_Y + 28)


def test_show_enter_leave():
    sm, scr, _ = make()
    sm.show("now_playing")
    sm.show("library")
    assert scr["now_playing"].log[-1] == ("leave",)
    assert scr["library"].log[-1][0] == "enter"
    assert sm.current_name() == "library"


def test_unknown_screen_raises_or_ignored():
    sm, scr, _ = make()
    sm.show("now_playing")
    sm.show("nope")
    assert sm.current_name() == "now_playing"


def test_push_pop_and_kwargs():
    sm, scr, _ = make()
    sm.show("library")
    sm.push("songs", mode="x")
    assert sm.current_name() == "songs"
    assert scr["songs"].log[-1] == ("enter", {"mode": "x"})
    assert sm.pop() is True
    assert sm.current_name() == "library"
    assert sm.pop() is False


def test_stack_bounded_no_duplicates():
    sm, scr, _ = make()
    sm.show("library")
    for _ in range(50):
        sm.push("songs")
        sm.push("artists")
        sm.push("albums")
    assert len(sm._stack) <= 4


def test_push_outside_library_tab_is_refused():
    sm, scr, _ = make()
    sm.show("settings")
    sm.push("songs")
    assert sm.current_name() == "settings"


def test_tab_tap_switches_and_resets_stack():
    sm, scr, _ = make()
    sm.show("library")
    sm.push("songs")
    c = tab_center(2)
    sm.handle_touch(c, "down")
    sm.handle_touch(c, "up")
    assert sm.current_name() == "queue"
    assert sm._stack == []
    c = tab_center(1)
    sm.handle_touch(c, "down")
    sm.handle_touch(c, "up")
    assert sm.current_name() == "library"
    sm.push("songs")
    sm.handle_touch(c, "down")
    sm.handle_touch(c, "up")  # re-tap active tab -> root
    assert sm.current_name() == "library"


def test_touch_routed_to_screen_and_gesture_captured():
    sm, scr, _ = make()
    sm.show("library")
    sm.handle_touch((100, 100), "down")
    sm.handle_touch((100, 500), "move")  # beyond content: still goes to same target
    sm.handle_touch((100, 500), "up")
    assert [k for _, k in scr["library"].touches] == ["down", "move", "up"]


def test_status_bar_touch_ignored():
    sm, scr, _ = make()
    sm.show("library")
    sm.handle_touch((100, 5), "down")
    assert scr["library"].touches == []


def test_mini_player_region_routes_to_mini():
    sm, scr, _ = make()

    class Mini:
        dirty = True
        def __init__(self): self.t = []
        def handle_touch(self, pos, kind): self.t.append(kind); return True
        def update(self, dt): pass
        def draw(self, surface): pass

    sm.mini_player = Mini()
    sm.show("library")
    sm.handle_touch((100, theme.MINI_Y + 10), "down")
    sm.handle_touch((100, theme.MINI_Y + 10), "up")
    assert sm.mini_player.t == ["down", "up"]
    assert scr["library"].touches == []
    sm.show("now_playing")  # no mini on now playing -> screen gets it
    sm.handle_touch((100, theme.MINI_Y + 10), "down")
    assert scr["now_playing"].touches


def test_toast_expires_and_dirty():
    sm, scr, surf = make()
    sm.show("library")
    sm.draw()
    sm.toast("Oops", "error")
    assert sm.toast_text == "Oops"
    rects = sm.draw()
    assert rects
    sm.update(10.0)
    assert sm.toast_text is None
    assert sm.draw()  # redraw to erase it


def test_sheet_modal_actions_and_dismiss():
    sm, scr, surf = make()
    sm.show("library")
    hits = []
    sm.show_sheet([("Play next", lambda: hits.append("a")), ("Add to queue", lambda: hits.append("b"))])
    assert sm.sheet_open
    sm.draw()
    sm.handle_touch((100, 100), "down")  # outside sheet: absorbed
    sm.handle_touch((100, 100), "up")
    assert not sm.sheet_open and scr["library"].touches == []
    sm.show_sheet([("Play next", lambda: hits.append("a")), ("Add to queue", lambda: hits.append("b"))])
    r = sm.sheet_row_rects()[1]
    assert r.height >= 44
    sm.handle_touch(r.center, "down")
    sm.handle_touch(r.center, "up")
    assert hits == ["b"] and not sm.sheet_open


def test_dirty_flag_redraw_and_idle_fps():
    sm, scr, surf = make()
    sm.show("library")
    assert sm.draw()               # first frame draws
    d = scr["library"].draws
    assert sm.draw() == []         # nothing dirty -> nothing drawn
    assert scr["library"].draws == d
    scr["library"].dirty = True
    assert sm.draw()
    assert scr["library"].draws == d + 1
    assert scr["library"].dirty is False
    sm.update(5.0)
    assert sm.target_fps() == theme.FPS_IDLE
    sm.handle_touch((100, 100), "down")
    assert sm.target_fps() == theme.FPS_ACTIVE


def test_screens_have_no_private_full_surface():
    sm, scr, _ = make()
    assert not hasattr(Screen(sm), "surface")


def test_overlay_drawn_and_dirty():
    sm, scr, surf = make()
    sm.show("library")
    sm.draw()

    class HUD:
        active = True
        dirty = True
        drawn = 0
        def update(self, dt): pass
        def draw(self, s): HUD.drawn += 1

    h = HUD()
    sm.add_overlay(h)
    assert sm.draw()
    assert HUD.drawn == 1


# ---- review fixes ----
def test_overlay_dirty_reset_after_hud_expires_real_hud():
    from ui.volume_hud import VolumeHUD
    sm, scr, surf = make()
    sm.show("library")
    sm.draw()
    hud = VolumeHUD()
    sm.add_overlay(hud)
    hud.show(50)
    assert sm.draw()
    sm.update(2.0)                       # HUD expires, needs one erase redraw
    assert sm.draw()
    assert sm.draw() == []               # no perpetual full redraws
    sm.update(2.0)
    assert sm.target_fps() == theme.FPS_IDLE


def test_overlay_stuck_dirty_flag_is_cleared():
    sm, scr, surf = make()
    sm.show("library")

    class O:
        active = False
        dirty = True
        def update(self, dt): pass
        def draw(self, s): pass

    o = O()
    sm.add_overlay(o)
    sm.draw()
    assert o.dirty is False
    assert sm.draw() == []


def test_idle_fps_reached_during_playback_with_periodic_redraw():
    sm, scr, surf = make()

    class Mini:
        dirty = True
        def handle_touch(self, pos, kind): return False
        def update(self, dt): pass
        def draw(self, s): self.dirty = False

    sm.mini_player = Mini()
    sm.show("library")
    sm.draw()
    fps = None
    for frame in range(60):              # 2 s at 30 fps, dirty once per second
        sm.update(1 / 30.0)
        if frame % 30 == 0:
            sm.mini_player.dirty = True
        sm.draw()
        fps = sm.target_fps()
    assert fps == theme.FPS_IDLE
    sm.handle_touch((100, 100), "down")
    assert sm.target_fps() == theme.FPS_ACTIVE


def test_continuous_animation_keeps_active_fps():
    sm, scr, surf = make()
    sm.show("library")
    for _ in range(60):
        sm.update(1 / 30.0)
        scr["library"].dirty = True
        sm.draw()
    assert sm.target_fps() == theme.FPS_ACTIVE


def test_status_bar_none_battery_default_and_hidden():
    from ui.screen_manager import StatusBar
    sb = StatusBar()
    assert sb.battery_level is None
    surf = pygame.Surface((320, 480))
    surf.fill((1, 2, 3))
    sb.draw(surf)
    blank = surf.subsurface((0, 0, 100, 22)).copy()
    sb.set_battery_level(80)
    assert sb.battery_level == 80
    sb.draw(surf)
    sb.set_battery_level(None)
    assert sb.battery_level is None and sb.dirty
    surf.fill((1, 2, 3))
    sb.draw(surf)
    again = surf.subsurface((0, 0, 100, 22))
    assert pygame.image.tostring(again, "RGB") == pygame.image.tostring(blank, "RGB")


def test_toast_does_not_overlap_volume_hud():
    from ui.volume_hud import VolumeHUD
    sm, scr, surf = make()
    sm.show("library")
    hud = VolumeHUD()
    assert not sm.toast_rect().colliderect(hud.rect)
    assert sm.toast_rect().bottom <= theme.TAB_Y


# ---- sub-rect dirty API ----
def test_sub_rect_redraw_returns_only_that_rect():
    sm, scr, surf = make()
    sm.show("library")
    sm.draw()
    assert sm.supports_dirty_rects is True
    s = scr["library"]
    d = s.draws
    r = pygame.Rect(20, 100, 100, 24)
    s.dirty_rects.append(r)
    rects = sm.draw()
    assert rects == [r]
    assert s.draws == d + 1 and s.dirty_rects == [] and s.dirty is False
    assert sm.draw() == []


def test_sub_rect_clipped_to_content_and_draw_clip_set():
    sm, scr, surf = make()
    clips = []

    class S(Rec):
        def draw(self, surface):
            clips.append(surface.get_clip())

    s = S(sm)
    sm.register("c", s, tab="queue")
    sm.show("c")
    sm.draw()
    clips.clear()
    s.dirty_rects.append(pygame.Rect(0, 400, 320, 200))   # runs past content bottom
    rects = sm.draw()
    assert rects == [pygame.Rect(0, 400, 320, theme.TAB_Y - 400)]
    assert clips == [rects[0]]


def test_full_dirty_still_wins_over_sub_rects():
    sm, scr, surf = make()
    sm.show("library")
    sm.draw()
    s = scr["library"]
    s.dirty = True
    s.dirty_rects.append(pygame.Rect(0, 100, 10, 10))
    rects = sm.draw()
    assert rects == [sm.content_rect()]
    assert s.dirty_rects == []


def test_repeated_sub_rect_redraws_do_not_hold_active_fps():
    sm, scr, surf = make()
    sm.show("library")
    sm.draw()
    s = scr["library"]
    for _ in range(60):
        sm.update(1 / 30.0)
        s.dirty_rects.append(pygame.Rect(20, 100, 100, 24))
        assert sm.draw() == [pygame.Rect(20, 100, 100, 24)]
    assert sm.target_fps() == theme.FPS_IDLE


def test_failed_screen_draw_restores_clip_and_repaints_everything():
    sm, scr, surf = make()
    painted = {"mini": 0}

    class Mini:
        dirty = True
        def handle_touch(self, pos, kind): return False
        def update(self, dt): pass
        def draw(self, s):
            painted["mini"] += 1
            self.dirty = False

    sm.mini_player = Mini()
    full_clip = surf.get_clip()
    sm.show("queue")
    sm.draw()
    boom = {"n": 1}
    orig = scr["now_playing"].draw

    def bad(surface):
        if boom["n"]:
            boom["n"] -= 1
            raise RuntimeError("draw failed")
    scr["now_playing"].draw = bad
    sm.show("now_playing")
    with pytest.raises(RuntimeError):
        sm.draw()
    assert surf.get_clip() == full_clip            # clip not stuck
    # switch tab; everything must repaint
    c = tab_center(2)
    sm.handle_touch(c, "down")
    sm.handle_touch(c, "up")
    before = painted["mini"]
    rects = sm.draw()
    assert sm.tab_bar.active == "queue"
    assert painted["mini"] == before + 1
    assert rects == [pygame.Rect(0, 0, theme.SCREEN_W, theme.SCREEN_H)]
    assert surf.get_clip() == full_clip


def test_failed_draw_sets_full_flag_for_retry():
    sm, scr, surf = make()
    sm.show("library")
    sm.draw()
    scr["library"].draw = lambda s: (_ for _ in ()).throw(ValueError("x"))
    scr["library"].dirty = True
    with pytest.raises(ValueError):
        sm.draw()
    assert sm._full is True

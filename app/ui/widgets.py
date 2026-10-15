"""Reusable widgets for the Pesto Player UI.

All widgets take absolute-coordinate pygame.Rect-like tuples, receive touches via
handle_touch(pos, kind) with kind in down|move|up|cancel, and set `dirty = True`
when they need a redraw. Nothing here creates fonts or surfaces per frame.
"""
import math
import time
from collections import deque

import pygame

from ui import text_cache, theme

# ---------------------------------------------------------------------------
# Icons (vector, drawn with polygons; no image assets)
# ---------------------------------------------------------------------------
def draw_icon(surface, name, rect, color):
    """Draw a simple icon centered in rect. Names: play pause next prev shuffle
    repeat repeat_one plus close check back menu."""
    rect = pygame.Rect(rect)
    cx, cy = rect.center
    s = min(rect.w, rect.h) * 0.5          # half-extent
    if name == "play":
        pygame.draw.polygon(surface, color, [(cx - s * .6, cy - s), (cx - s * .6, cy + s), (cx + s, cy)])
    elif name == "pause":
        w = max(2, int(s * .5))
        pygame.draw.rect(surface, color, (cx - s * .7, cy - s * .9, w, s * 1.8))
        pygame.draw.rect(surface, color, (cx + s * .7 - w, cy - s * .9, w, s * 1.8))
    elif name == "next":
        pygame.draw.polygon(surface, color, [(cx - s, cy - s * .8), (cx - s, cy + s * .8), (cx + s * .5, cy)])
        pygame.draw.rect(surface, color, (cx + s * .6, cy - s * .8, max(2, s * .25), s * 1.6))
    elif name == "prev":
        pygame.draw.polygon(surface, color, [(cx + s, cy - s * .8), (cx + s, cy + s * .8), (cx - s * .5, cy)])
        pygame.draw.rect(surface, color, (cx - s * .85, cy - s * .8, max(2, s * .25), s * 1.6))
    elif name in ("shuffle",):
        pygame.draw.lines(surface, color, False, [(cx - s, cy + s * .6), (cx - s * .2, cy + s * .6),
                                                  (cx + s * .3, cy - s * .6), (cx + s * .8, cy - s * .6)], 2)
        pygame.draw.lines(surface, color, False, [(cx - s, cy - s * .6), (cx - s * .2, cy - s * .6),
                                                  (cx + s * .3, cy + s * .6), (cx + s * .8, cy + s * .6)], 2)
        pygame.draw.polygon(surface, color, [(cx + s * .7, cy - s), (cx + s, cy - s * .6), (cx + s * .7, cy - s * .2)])
        pygame.draw.polygon(surface, color, [(cx + s * .7, cy + s * .2), (cx + s, cy + s * .6), (cx + s * .7, cy + s)])
    elif name in ("repeat", "repeat_one"):
        r = pygame.Rect(0, 0, s * 2, s * 1.3)
        r.center = (cx, cy)
        pygame.draw.rect(surface, color, r, 2, border_radius=int(s * .5))
        pygame.draw.polygon(surface, color, [(cx + s * .2, r.top - 4), (cx + s * .2, r.top + 4), (cx + s * .6, r.top)])
        if name == "repeat_one":
            f = text_cache.render("1", max(10, int(s)), color, bold=True)
            surface.blit(f, f.get_rect(center=(cx, cy)))
    elif name == "plus":
        pygame.draw.line(surface, color, (cx - s * .7, cy), (cx + s * .7, cy), 3)
        pygame.draw.line(surface, color, (cx, cy - s * .7), (cx, cy + s * .7), 3)
    elif name == "close":
        pygame.draw.line(surface, color, (cx - s * .6, cy - s * .6), (cx + s * .6, cy + s * .6), 3)
        pygame.draw.line(surface, color, (cx - s * .6, cy + s * .6), (cx + s * .6, cy - s * .6), 3)
    elif name == "check":
        pygame.draw.lines(surface, color, False, [(cx - s * .7, cy), (cx - s * .2, cy + s * .5), (cx + s * .7, cy - s * .5)], 3)
    elif name == "back":
        pygame.draw.lines(surface, color, False, [(cx + s * .4, cy - s * .8), (cx - s * .4, cy), (cx + s * .4, cy + s * .8)], 3)
    elif name == "menu":
        for dy in (-s * .6, 0, s * .6):
            pygame.draw.line(surface, color, (cx - s * .7, cy + dy), (cx + s * .7, cy + dy), 3)


# ---------------------------------------------------------------------------
# Button
# ---------------------------------------------------------------------------
_STYLES = {
    "primary": (theme.PRIMARY, theme.PRIMARY_DARK, theme.TEXT),
    "secondary": (theme.BG_LIGHT, theme.BG_PRESSED, theme.TEXT),
    "ghost": (None, theme.BG_PRESSED, theme.TEXT),
    "danger": (theme.ERROR, (160, 50, 50), theme.TEXT),
}


class Button:
    """Tap button. Press highlights; dragging out or cancel resets without firing."""

    def __init__(self, rect, text="", on_click=None, icon=None, style="primary", enabled=True):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.on_click = on_click
        self.icon = icon
        self.style = style
        self.enabled = enabled
        self.pressed = False
        self.active = False       # toggled look (e.g. shuffle on)
        self.dirty = True

    def _set_pressed(self, v):
        if self.pressed != v:
            self.pressed = v
            self.dirty = True

    def handle_touch(self, pos, kind):
        if not self.enabled:
            return False
        inside = self.rect.collidepoint(pos)
        if kind == "down":
            if inside:
                self._set_pressed(True)
                return True
            return False
        if kind == "move":
            if self.pressed and not inside:
                self._set_pressed(False)
            return self.pressed
        if kind == "up":
            fire = self.pressed and inside
            was = self.pressed
            self._set_pressed(False)
            if fire and self.on_click:
                self.on_click()
            return was
        if kind == "cancel":
            was = self.pressed
            self._set_pressed(False)
            return was
        return False

    def draw(self, surface):
        bg, pressed_bg, fg = _STYLES.get(self.style, _STYLES["primary"])
        if not self.enabled:
            fg = theme.TEXT_DISABLED
        if self.active:
            fg = theme.PRIMARY_LIGHT
        col = pressed_bg if self.pressed else bg
        if col is not None:
            pygame.draw.rect(surface, col, self.rect, border_radius=8)
        if self.icon:
            draw_icon(surface, self.icon, self.rect, fg)
        if self.text:
            img = text_cache.render(text_cache.ellipsize(self.text, theme.FS_BODY, self.rect.w - 8, True),
                                    theme.FS_BODY, fg, bold=True)
            surface.blit(img, img.get_rect(center=self.rect.center))
        self.dirty = False


# ---------------------------------------------------------------------------
# ScrollList
# ---------------------------------------------------------------------------
class ScrollList:
    """Virtualised kinetic list. Draws only visible rows via draw_row.

    draw_row(surface, rect, item, index, state): state is {"pressed": bool}.
    Tap = total travel <= TAP_SLOP and press <= TAP_MAX_MS. A drag, a slow press or
    a long press never calls on_tap. `clock` is injectable for tests.
    """
    FRICTION = 3.0        # exp decay per second
    MIN_V = 15.0          # px/s below which a flick stops
    FLICK_WINDOW = 0.1    # s of recent motion used for release velocity

    def __init__(self, rect, row_h, draw_row, on_tap=None, on_long_press=None, items=None):
        self.rect = pygame.Rect(rect)
        self.row_h = row_h
        self.draw_row = draw_row
        self.on_tap = on_tap
        self.on_long_press = on_long_press
        self.items = list(items or [])
        self.scroll = 0.0
        self.dirty = True
        self.clock = time.monotonic
        self._reset_touch()
        self.velocity = 0.0

    def _reset_touch(self):
        self._down = False
        self._start = (0, 0)
        self._start_scroll = 0.0
        self._t0 = 0.0
        self._dragging = False
        self._long_fired = False
        self._pressed_idx = None
        self._samples = deque(maxlen=8)

    # --- data ---
    def set_items(self, items):
        self.items = list(items)
        self.scroll = self._clamp(self.scroll)
        self._pressed_idx = None
        self.dirty = True

    def max_scroll(self):
        return max(0, len(self.items) * self.row_h - self.rect.h)

    def _clamp(self, v):
        return max(0.0, min(float(self.max_scroll()), v))

    def scroll_to_index(self, index):
        self.scroll = self._clamp(index * self.row_h)
        self.velocity = 0.0
        self.dirty = True

    def index_at(self, pos):
        if not self.rect.collidepoint(pos):
            return None
        i = int((pos[1] - self.rect.y + self.scroll) // self.row_h)
        return i if 0 <= i < len(self.items) else None

    # --- touch ---
    def handle_touch(self, pos, kind):
        now = self.clock()
        if kind == "down":
            if not self.rect.collidepoint(pos):
                return False
            self.velocity = 0.0                      # a new touch stops any flick
            self._reset_touch()
            self._down = True
            self._start = pos
            self._start_scroll = self.scroll
            self._t0 = now
            self._pressed_idx = self.index_at(pos)
            self._samples.append((now, pos[1]))
            self.dirty = True
            return True
        if not self._down:
            return False
        if kind == "move":
            self._samples.append((now, pos[1]))
            travel = math.hypot(pos[0] - self._start[0], pos[1] - self._start[1])
            if not self._dragging and travel > theme.TAP_SLOP:
                self._dragging = True
                self._pressed_idx = None
            if self._dragging and not self._long_fired:
                new = self._clamp(self._start_scroll - (pos[1] - self._start[1]))
                if new != self.scroll:
                    self.scroll = new
                self.dirty = True
            return True
        if kind == "up":
            self._samples.append((now, pos[1]))
            travel = math.hypot(pos[0] - self._start[0], pos[1] - self._start[1])
            idx = self._pressed_idx
            quick = (now - self._t0) * 1000.0 <= theme.TAP_MAX_MS
            is_tap = (not self._dragging and not self._long_fired and travel <= theme.TAP_SLOP and quick)
            was_drag = self._dragging
            self._pressed_idx = None
            self._down = False
            self.dirty = True
            if is_tap and idx is not None and self.on_tap:
                self.on_tap(self.items[idx], idx)
            elif was_drag:
                self.velocity = self._release_velocity(now)
            return True
        if kind == "cancel":
            self._reset_touch()
            self.dirty = True
            return True
        return False

    def _release_velocity(self, now):
        recent = [(t, y) for t, y in self._samples if now - t <= self.FLICK_WINDOW]
        if len(recent) < 2:
            return 0.0
        (t0, y0), (t1, y1) = recent[0], recent[-1]
        dt = t1 - t0
        if dt <= 0:
            return 0.0
        return -(y1 - y0) / dt          # px/s of scroll offset

    def update(self, dt):
        if self._down and not self._dragging and not self._long_fired and self.on_long_press:
            if (self.clock() - self._t0) * 1000.0 >= theme.LONG_PRESS_MS:
                idx = self._pressed_idx
                if idx is not None:
                    self._long_fired = True
                    self._pressed_idx = None
                    self.dirty = True
                    self.on_long_press(self.items[idx], idx)
        if self.velocity:
            self.scroll = self._clamp(self.scroll + self.velocity * dt)
            self.velocity *= math.exp(-self.FRICTION * dt)
            if abs(self.velocity) < self.MIN_V or self.scroll in (0.0, float(self.max_scroll())):
                self.velocity = 0.0
            self.dirty = True

    # --- draw ---
    def draw(self, surface):
        prev = surface.get_clip()
        surface.set_clip(self.rect)
        n = len(self.items)
        if n:
            first = int(self.scroll // self.row_h)
            last = min(n - 1, int((self.scroll + self.rect.h) // self.row_h))
            for i in range(max(0, first), last + 1):
                r = pygame.Rect(self.rect.x, int(self.rect.y + i * self.row_h - self.scroll),
                                self.rect.w, self.row_h)
                self.draw_row(surface, r, self.items[i], i, {"pressed": i == self._pressed_idx})
            total = n * self.row_h
            if total > self.rect.h:
                bar_h = max(20, int(self.rect.h * self.rect.h / total))
                frac = self.scroll / (total - self.rect.h)
                y = self.rect.y + int((self.rect.h - bar_h) * frac)
                pygame.draw.rect(surface, theme.BORDER, (self.rect.right - 3, y, 3, bar_h), border_radius=1)
        surface.set_clip(prev)
        self.dirty = False


# ---------------------------------------------------------------------------
# Slider
# ---------------------------------------------------------------------------
class Slider:
    """Horizontal 0..1 slider with a >= 44 px vertical hit zone. on_change while
    dragging, on_commit once on release (seek-on-release semantics)."""
    TRACK_H = 6

    def __init__(self, rect, value=0.0, on_change=None, on_commit=None):
        self.rect = pygame.Rect(rect)
        self.value = float(value)
        self.on_change = on_change
        self.on_commit = on_commit
        self.dragging = False
        self.dirty = True

    def hit_rect(self):
        h = max(theme.MIN_TOUCH, self.rect.h)
        r = pygame.Rect(self.rect.x, 0, self.rect.w, h)
        r.centery = self.rect.centery
        return r

    def set_value(self, v):
        v = max(0.0, min(1.0, float(v)))
        if not self.dragging and v != self.value:
            self.value = v
            self.dirty = True

    def _value_at(self, x):
        return max(0.0, min(1.0, (x - self.rect.x) / float(max(1, self.rect.w))))

    def handle_touch(self, pos, kind):
        if kind == "down":
            if self.hit_rect().collidepoint(pos):
                self.dragging = True
                self.value = self._value_at(pos[0])
                self.dirty = True
                if self.on_change:
                    self.on_change(self.value)
                return True
            return False
        if not self.dragging:
            return False
        if kind == "move":
            self.value = self._value_at(pos[0])
            self.dirty = True
            if self.on_change:
                self.on_change(self.value)
            return True
        if kind == "up":
            self.value = self._value_at(pos[0])
            self.dragging = False
            self.dirty = True
            if self.on_commit:
                self.on_commit(self.value)
            return True
        if kind == "cancel":
            self.dragging = False
            self.dirty = True
            return True
        return False

    def draw(self, surface):
        cy = self.rect.centery
        track = pygame.Rect(self.rect.x, cy - self.TRACK_H // 2, self.rect.w, self.TRACK_H)
        pygame.draw.rect(surface, theme.BORDER, track, border_radius=3)
        fill = track.copy()
        fill.w = int(track.w * self.value)
        if fill.w > 0:
            pygame.draw.rect(surface, theme.PRIMARY, fill, border_radius=3)
        r = 9 if self.dragging else 7
        pygame.draw.circle(surface, theme.TEXT, (track.x + fill.w, cy), r)
        self.dirty = False


# ---------------------------------------------------------------------------
# TabBar
# ---------------------------------------------------------------------------
class TabBar:
    """Bottom tab bar. tabs = [(name, label), ...]; on_select(name) fires on release."""

    def __init__(self, rect, tabs, on_select=None):
        self.rect = pygame.Rect(rect)
        self.tabs = list(tabs)
        self.on_select = on_select
        self.active = self.tabs[0][0] if self.tabs else None
        self._down = None
        self.dirty = True

    def _cell(self, i):
        w = self.rect.w / float(len(self.tabs))
        return pygame.Rect(int(self.rect.x + i * w), self.rect.y, int(w), self.rect.h)

    def _index_at(self, pos):
        if not self.tabs or not self.rect.collidepoint(pos):
            return None
        return min(len(self.tabs) - 1, int((pos[0] - self.rect.x) // (self.rect.w / float(len(self.tabs)))))

    def set_active(self, name):
        if name != self.active:
            self.active = name
            self.dirty = True

    def handle_touch(self, pos, kind):
        if kind == "down":
            self._down = self._index_at(pos)
            self.dirty = True
            return self._down is not None
        if self._down is None:
            return False
        if kind == "up":
            idx = self._index_at(pos)
            hit = self._down
            self._down = None
            self.dirty = True
            if idx == hit and self.on_select:
                self.on_select(self.tabs[idx][0])
            return True
        if kind == "cancel":
            self._down = None
            self.dirty = True
            return True
        return True

    def draw(self, surface):
        pygame.draw.rect(surface, theme.BG_DARK, self.rect)
        pygame.draw.line(surface, theme.BORDER, self.rect.topleft, self.rect.topright)
        for i, (name, label) in enumerate(self.tabs):
            cell = self._cell(i)
            on = name == self.active
            if self._down == i:
                pygame.draw.rect(surface, theme.BG_PRESSED, cell)
            col = theme.PRIMARY_LIGHT if on else theme.TEXT_DIM
            if on:
                pygame.draw.rect(surface, theme.PRIMARY, (cell.x + 12, cell.y + 1, cell.w - 24, 3))
            img = text_cache.render(label, theme.FS_SMALL + 1, col, bold=on)
            surface.blit(img, img.get_rect(center=cell.center))
        self.dirty = False


# ---------------------------------------------------------------------------
# Marquee
# ---------------------------------------------------------------------------
class Marquee:
    """Single-line text that scrolls horizontally only when it overflows."""
    SPEED = 30       # px/s
    PAUSE = 1.2      # s hold at start
    GAP = 40         # px between repeats

    def __init__(self, rect, text="", size=theme.FS_TITLE, color=theme.TEXT, bold=False):
        self.rect = pygame.Rect(rect)
        self.size = size
        self.color = color
        self.bold = bold
        self.text = ""
        self.offset = 0
        self._t = 0.0
        self._w = 0
        self.dirty = True
        self.set_text(text)

    def set_text(self, text):
        if text != self.text or not self._w:
            self.text = text
            self._w = text_cache.text_width(text, self.size, self.bold) if text else 0
            self.offset = 0
            self._t = 0.0
            self.dirty = True

    def overflows(self):
        return self._w > self.rect.w

    def update(self, dt):
        if not self.overflows():
            return
        self._t += dt
        if self._t < self.PAUSE:
            return
        cycle = self._w + self.GAP
        off = int(((self._t - self.PAUSE) * self.SPEED) % cycle)
        if off != self.offset:
            self.offset = off
            self.dirty = True

    def draw(self, surface):
        if self.text:
            img = text_cache.render(self.text, self.size, self.color, self.bold)
            prev = surface.get_clip()
            surface.set_clip(self.rect)
            y = self.rect.y + (self.rect.h - img.get_height()) // 2
            if self.overflows():
                surface.blit(img, (self.rect.x - self.offset, y))
                surface.blit(img, (self.rect.x - self.offset + self._w + self.GAP, y))
            else:
                surface.blit(img, (self.rect.x, y))
            surface.set_clip(prev)
        self.dirty = False

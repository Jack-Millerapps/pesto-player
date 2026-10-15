"""Screen manager: persistent shell (status bar, optional mini-player, tab bar)
hosting screens, with tab-aware navigation, toast, action sheet and overlays.

Design:
- Four fixed tabs; each registered screen belongs to at most one tab. The first
  screen registered for a tab is that tab's root. push()/pop() are allowed only
  inside the Library tab and the stack is bounded (no unbounded history).
- Screens draw into the shared display surface (clipped to the content rect); there
  is no per-Screen full-size surface.
- draw() redraws only dirty regions and returns the list of dirty rects so the
  launcher can push just those rows. target_fps() drops to FPS_IDLE when idle.
"""
import pygame

from ui import text_cache, theme
from ui.widgets import TabBar

TABS = [("now_playing", "Now Playing"), ("library", "Library"),
        ("queue", "Queue"), ("settings", "Settings")]
PUSH_TAB = "library"
MAX_STACK = 4
TOAST_S = 2.5
SHEET_ROW_H = 48


class Screen:
    """Base class. Subclasses override what they need.

    kind in handle_touch is one of down|move|up|cancel. Set `dirty = True` to
    request a redraw. Set has_mini_player = False to hide the mini-player.
    """
    has_mini_player = True

    def __init__(self, screen_manager=None):
        self.screen_manager = screen_manager
        self.dirty = True

    def on_enter(self, **kw):
        pass

    def on_leave(self):
        pass

    def handle_touch(self, pos, kind):
        return False

    def update(self, dt):
        pass

    def draw(self, surface):
        pass


class StatusBar:
    """Top status bar: battery (left) and Bluetooth indicator (right)."""

    def __init__(self):
        self.battery_level = 100
        self.bluetooth_connected = False
        self.dirty = True

    def set_battery_level(self, level):
        level = max(0, min(100, int(level)))
        if level != self.battery_level:
            self.battery_level = level
            self.dirty = True

    def set_bluetooth_connected(self, connected):
        if bool(connected) != self.bluetooth_connected:
            self.bluetooth_connected = bool(connected)
            self.dirty = True

    def draw(self, surface):
        r = pygame.Rect(0, 0, theme.SCREEN_W, theme.STATUS_H)
        pygame.draw.rect(surface, theme.BG_DARK, r)
        pygame.draw.line(surface, theme.BORDER, (0, r.bottom - 1), (r.right, r.bottom - 1))
        lvl = self.battery_level
        col = theme.ERROR if lvl <= 5 else theme.WARNING if lvl <= 15 else theme.SUCCESS
        bx, by = theme.PAD, 6
        pygame.draw.rect(surface, theme.TEXT_DIM, (bx, by, 26, 12), 1)
        pygame.draw.rect(surface, theme.TEXT_DIM, (bx + 26, by + 3, 2, 6))
        fw = int(22 * lvl / 100.0)
        if fw > 0:
            pygame.draw.rect(surface, col, (bx + 2, by + 2, fw, 8))
        img = text_cache.render("%d%%" % lvl, theme.FS_SMALL, theme.TEXT_DIM)
        surface.blit(img, (bx + 34, (theme.STATUS_H - img.get_height()) // 2))
        if self.bluetooth_connected:
            img = text_cache.render("BT", theme.FS_SMALL, theme.PRIMARY_LIGHT, bold=True)
            surface.blit(img, (r.right - theme.PAD - img.get_width(), (theme.STATUS_H - img.get_height()) // 2))
        self.dirty = False


class ScreenManager:
    def __init__(self, display_surface):
        self.display_surface = display_surface
        self.status_bar = StatusBar()
        self.mini_player = None            # object with draw/handle_touch/update/dirty
        self.tab_bar = TabBar((0, theme.TAB_Y, theme.SCREEN_W, theme.TAB_H), TABS, self._on_tab)
        self._screens = {}                 # name -> (screen, tab)
        self._tab_root = {}                # tab -> root screen name
        self._cur = None
        self._stack = []
        self._overlays = []
        self._full = True
        self._idle = 0.0
        self._capture = None               # touch gesture target
        self.toast_text = None
        self.toast_kind = "info"
        self._toast_t = 0.0
        self._toast_dirty = False
        self._sheet = None                 # list of (label, callable)
        self._sheet_down = None
        self._sheet_dirty = False
        self._overlay_was_active = False

    # ---------------- registration / navigation ----------------
    def register(self, name, screen, tab=None):
        self._screens[name] = (screen, tab)
        if tab is not None and tab not in self._tab_root:
            self._tab_root[tab] = name
        if screen.screen_manager is None:
            screen.screen_manager = self

    def current_name(self):
        return self._cur

    def current_screen(self):
        return self._screens[self._cur][0] if self._cur else None

    def _tab_of(self, name):
        return self._screens[name][1] if name in self._screens else None

    def _switch(self, name, kw):
        old = self.current_screen()
        if old is not None:
            old.on_leave()
        self._cur = name
        scr = self._screens[name][0]
        self.tab_bar.set_active(self._tab_of(name))
        self._full = True
        scr.dirty = True
        scr.on_enter(**kw)

    def show(self, name, **kw):
        """Show a screen (tab root or any registered screen); clears the nav stack."""
        if name not in self._screens:
            print("ScreenManager: unknown screen %r" % name)
            return
        self._stack = []
        self._switch(name, kw)

    def push(self, name, **kw):
        """Navigate deeper inside the Library tab (bounded stack)."""
        if name not in self._screens or self._cur is None:
            return
        if self._tab_of(self._cur) != PUSH_TAB or self._tab_of(name) != PUSH_TAB:
            return
        if name == self._cur:
            return
        if name in self._stack:                     # going "back" to something already visited
            self._stack = self._stack[:self._stack.index(name)]
        else:
            self._stack.append(self._cur)
            if len(self._stack) > MAX_STACK:
                del self._stack[1]                  # keep the root, drop oldest middle
        self._switch(name, kw)

    def pop(self):
        if not self._stack:
            return False
        name = self._stack.pop()
        self._switch(name, {})
        return True

    def _on_tab(self, tab):
        root = self._tab_root.get(tab)
        if root is not None:
            self.show(root)

    # ---------------- overlays ----------------
    def toast(self, msg, kind="info"):
        self.toast_text = msg
        self.toast_kind = kind
        self._toast_t = TOAST_S
        self._toast_dirty = True
        self._idle = 0.0

    def show_sheet(self, actions):
        self._sheet = list(actions)
        self._sheet_down = None
        self._sheet_dirty = True
        self._idle = 0.0

    @property
    def sheet_open(self):
        return self._sheet is not None

    def _sheet_rects(self):
        n = len(self._sheet or [])
        total = (n + 1) * SHEET_ROW_H + 8
        top = theme.SCREEN_H - total
        rows = [pygame.Rect(0, top + 8 + i * SHEET_ROW_H, theme.SCREEN_W, SHEET_ROW_H) for i in range(n)]
        cancel = pygame.Rect(0, top + 8 + n * SHEET_ROW_H, theme.SCREEN_W, SHEET_ROW_H)
        return pygame.Rect(0, top, theme.SCREEN_W, total), rows, cancel

    def sheet_row_rects(self):
        return self._sheet_rects()[1] if self._sheet is not None else []

    def _close_sheet(self):
        self._sheet = None
        self._sheet_down = None
        self._sheet_dirty = True
        self._full = True

    def add_overlay(self, overlay):
        """Overlay: object with active, dirty, update(dt), draw(surface)."""
        self._overlays.append(overlay)

    # ---------------- frame loop ----------------
    def _mini_visible(self):
        scr = self.current_screen()
        return self.mini_player is not None and scr is not None and scr.has_mini_player

    def content_rect(self):
        bottom = theme.MINI_Y if self._mini_visible() else theme.TAB_Y
        return pygame.Rect(0, theme.STATUS_H, theme.SCREEN_W, bottom - theme.STATUS_H)

    def update(self, dt):
        self._idle += dt
        scr = self.current_screen()
        if scr is not None:
            scr.update(dt)
        if self._mini_visible():
            self.mini_player.update(dt)
        for o in self._overlays:
            o.update(dt)
        if self.toast_text is not None:
            self._toast_t -= dt
            if self._toast_t <= 0:
                self.toast_text = None
                self._toast_dirty = True
                self._full = True

    def target_fps(self):
        return theme.FPS_IDLE if self._idle >= theme.IDLE_AFTER_S else theme.FPS_ACTIVE

    def _draw_toast(self, surface):
        col = {"error": theme.ERROR, "warn": theme.WARNING, "success": theme.SUCCESS}.get(self.toast_kind, theme.PRIMARY)
        r = pygame.Rect(theme.PAD, theme.STATUS_H + 6, theme.SCREEN_W - 2 * theme.PAD, 36)
        pygame.draw.rect(surface, theme.TOAST_BG, r, border_radius=8)
        pygame.draw.rect(surface, col, r, 2, border_radius=8)
        txt = text_cache.ellipsize(self.toast_text, theme.FS_BODY, r.w - 20)
        img = text_cache.render(txt, theme.FS_BODY, theme.TEXT)
        surface.blit(img, img.get_rect(center=r.center))

    def _draw_sheet(self, surface):
        panel, rows, cancel = self._sheet_rects()
        pygame.draw.rect(surface, theme.BG_LIGHT, panel)
        pygame.draw.line(surface, theme.PRIMARY, panel.topleft, panel.topright, 2)
        for i, ((label, _), r) in enumerate(zip(self._sheet, rows)):
            if self._sheet_down == i:
                pygame.draw.rect(surface, theme.BG_PRESSED, r)
            img = text_cache.render(text_cache.ellipsize(label, theme.FS_TITLE, r.w - 32), theme.FS_TITLE, theme.TEXT)
            surface.blit(img, (theme.PAD + 4, r.centery - img.get_height() // 2))
        if self._sheet_down == len(rows):
            pygame.draw.rect(surface, theme.BG_PRESSED, cancel)
        img = text_cache.render("Cancel", theme.FS_TITLE, theme.TEXT_DIM)
        surface.blit(img, (theme.PAD + 4, cancel.centery - img.get_height() // 2))

    def draw(self):
        """Redraw dirty regions. Returns list of dirty pygame.Rects (empty = nothing)."""
        surf = self.display_surface
        scr = self.current_screen()
        if scr is None:
            return []
        overlay_active = any(getattr(o, "active", False) for o in self._overlays)
        overlay_dirty = overlay_active or self._overlay_was_active or any(getattr(o, "dirty", False) for o in self._overlays)
        over = self.toast_text is not None or self._sheet is not None or overlay_active
        mini_vis = self._mini_visible()
        content = self.content_rect()
        status_d = self.status_bar.dirty
        content_d = scr.dirty
        mini_d = mini_vis and getattr(self.mini_player, "dirty", True)
        tab_d = self.tab_bar.dirty
        any_dirty = status_d or content_d or mini_d or tab_d
        overlay_changed = self._toast_dirty or self._sheet_dirty or overlay_dirty
        full = self._full or (over and (any_dirty or overlay_changed)) or (not over and overlay_changed)
        if not (full or any_dirty):
            return []
        rects = []
        if full or status_d:
            self.status_bar.draw(surf)
            rects.append(pygame.Rect(0, 0, theme.SCREEN_W, theme.STATUS_H))
        if full or content_d:
            prev = surf.get_clip()
            surf.set_clip(content)
            pygame.draw.rect(surf, theme.BG, content)
            scr.draw(surf)
            surf.set_clip(prev)
            scr.dirty = False
            rects.append(content)
        if mini_vis and (full or mini_d):
            self.mini_player.draw(surf)
            rects.append(pygame.Rect(0, theme.MINI_Y, theme.SCREEN_W, theme.MINI_H))
        if full or tab_d:
            self.tab_bar.draw(surf)
            rects.append(pygame.Rect(0, theme.TAB_Y, theme.SCREEN_W, theme.TAB_H))
        if full:
            for o in self._overlays:
                if getattr(o, "active", False):
                    o.draw(surf)
            if self.toast_text is not None:
                self._draw_toast(surf)
            if self._sheet is not None:
                self._draw_sheet(surf)
            rects = [pygame.Rect(0, 0, theme.SCREEN_W, theme.SCREEN_H)]
        self._full = False
        self._toast_dirty = False
        self._sheet_dirty = False
        self._overlay_was_active = overlay_active
        if rects:
            self._idle = 0.0
        return rects

    # ---------------- touch ----------------
    def handle_touch(self, pos, kind):
        if kind == "down":
            self._idle = 0.0
            self._capture = self._target_at(pos)
        elif kind in ("move", "up", "cancel"):
            self._idle = 0.0
        tgt = self._capture
        if kind in ("up", "cancel"):
            self._capture = None
        if tgt is None:
            return False
        if tgt == "sheet":
            return self._sheet_touch(pos, kind)
        if tgt == "tab":
            return self.tab_bar.handle_touch(pos, kind)
        if tgt == "mini":
            return bool(self.mini_player.handle_touch(pos, kind))
        scr = self.current_screen()
        return bool(scr.handle_touch(pos, kind)) if scr else False

    def _target_at(self, pos):
        if self._sheet is not None:
            return "sheet"
        if pos[1] < theme.STATUS_H:
            return None
        if pos[1] >= theme.TAB_Y:
            return "tab"
        if self._mini_visible() and pos[1] >= theme.MINI_Y:
            return "mini"
        return "screen"

    def _sheet_touch(self, pos, kind):
        if self._sheet is None:
            return True
        panel, rows, cancel = self._sheet_rects()
        def hit(p):
            for i, r in enumerate(rows):
                if r.collidepoint(p):
                    return i
            if cancel.collidepoint(p):
                return len(rows)
            return -1 if not panel.collidepoint(p) else None
        if kind == "down":
            self._sheet_down = hit(pos)
            self._sheet_dirty = True
        elif kind == "up":
            h = hit(pos)
            d = self._sheet_down
            actions = self._sheet
            if d == -1 and h == -1:                 # tapped outside
                self._close_sheet()
            elif d is not None and d == h:
                self._close_sheet()
                if h < len(actions):
                    actions[h][1]()
            else:
                self._sheet_down = None
                self._sheet_dirty = True
        elif kind == "cancel":
            self._sheet_down = None
            self._sheet_dirty = True
        return True

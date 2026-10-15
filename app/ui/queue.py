"""Queue screen: shows the play queue; tap plays, long-press for move/remove.

Header (48 px): title + Save (as playlist) + Clear. The list sits above the
mini-player. Rows have an "x" remove zone (44 px wide). Reorder goes through the
long-press sheet (Move up / Move down) to avoid accidental drags while scrolling.
"""
import time

import pygame

from ui import theme, text_cache
from ui.screen_manager import Screen
from ui.widgets import ScrollList
from ui.now_playing import track_title, track_artist, fmt_time

POLL_S = 0.2
HEADER_H = 48
X_ZONE = 44


class QueueScreen(Screen):
    has_mini_player = True

    def __init__(self, screen_manager, audio_player, music_library=None, playlist_store=None):
        super().__init__(screen_manager)
        self.audio = audio_player
        self.library = music_library
        self._store = playlist_store
        top = theme.CONTENT_TOP + HEADER_H
        self.list_rect = pygame.Rect(0, top, theme.SCREEN_W, theme.CONTENT_BOTTOM_MINI - top)
        self.clear_rect = pygame.Rect(theme.SCREEN_W - theme.PAD - 64, theme.CONTENT_TOP + 2, 64, theme.MIN_TOUCH)
        self.save_rect = pygame.Rect(self.clear_rect.left - 8 - 64, theme.CONTENT_TOP + 2, 64, theme.MIN_TOUCH)
        self.list = ScrollList(self.list_rect, theme.ROW_H, self._draw_row,
                               on_tap=self._on_row_tap, on_long_press=self.on_long_press, items=[])
        self.items = []
        self.current_index = -1
        self._sig = None
        self._acc = POLL_S
        self._pressed = None
        self._last_down_x = None

    @property
    def store(self):
        if self._store is None:
            from player.playlist import PlaylistStore
            self._store = PlaylistStore()
        return self._store

    # ---- lifecycle / state -----------------------------------------------
    def on_enter(self, **kw):
        self._acc = POLL_S
        self._pressed = None
        self.refresh()

    def on_leave(self):
        self._pressed = None

    def is_empty(self):
        return not self.items

    def refresh(self):
        try:
            q = self.audio.get_queue() or []
            idx = (self.audio.get_state() or {}).get("queue_index", -1)
        except Exception:
            q, idx = [], -1
        sig = (tuple(t.get("id") for t in q), idx)
        if sig != self._sig:
            self._sig = sig
            self.items = list(q)
            self.current_index = idx
            self.list.set_items(self.items)
            self.dirty = True

    def update(self, dt):
        self._acc += dt
        if self._acc >= POLL_S:
            self._acc = 0.0
            self.refresh()
        if hasattr(self.list, "update"):
            self.list.update(dt)
        if getattr(self.list, "dirty", False):
            self.dirty = True

    # ---- actions -----------------------------------------------------------
    def _on_row_tap(self, item, index):
        # A's ScrollList reports a tap on the x zone only through on_tap, so split here.
        x = getattr(self, "_last_down_x", None)
        if x is not None and x >= theme.SCREEN_W - X_ZONE:
            self.on_remove(index)
        else:
            self.on_tap(item, index)

    def on_tap(self, item, index):
        self.audio.set_queue(self.audio.get_queue(), index)

    def on_remove(self, index):
        if 0 <= index < len(self.items):
            self.audio.remove_from_queue(index)
            self.refresh()
            self.dirty = True

    def on_move(self, src, dst):
        if 0 <= dst < len(self.items) and 0 <= src < len(self.items):
            self.audio.move_in_queue(src, dst)
            self.refresh()

    def on_long_press(self, item, index):
        n = len(self.items)
        actions = [("Play now", lambda i=index: self.on_tap(None, i))]
        if index > 0:
            actions.append(("Move up", lambda i=index: self.on_move(i, i - 1)))
        if index < n - 1:
            actions.append(("Move down", lambda i=index: self.on_move(i, i + 1)))
        actions.append(("Remove", lambda i=index: self.on_remove(i)))
        self.screen_manager.show_sheet(actions)

    def clear(self):
        self.audio.set_queue([], 0)
        self.refresh()
        self.dirty = True

    def save_as_playlist(self):
        if not self.items:
            self.screen_manager.toast("Queue is empty", "info")
            return
        name = "Queue " + time.strftime("%Y-%m-%d %H:%M")
        try:
            self.store.save(name, list(self.items))
        except Exception as e:
            self.screen_manager.toast("Could not save: %s" % e, "error")
            return
        self.screen_manager.toast("Saved as '%s'" % name, "info")

    # ---- touch ---------------------------------------------------------------
    def handle_touch(self, pos, kind):
        if kind == "down":
            self._last_down_x = pos[0]
            for name, rect in (("save", self.save_rect), ("clear", self.clear_rect)):
                if rect.collidepoint(pos):
                    self._pressed = name
                    self.dirty = True
                    return True
        elif kind == "move" and self._pressed:
            rect = self.save_rect if self._pressed == "save" else self.clear_rect
            if not rect.collidepoint(pos):
                self._pressed = None
                self.dirty = True
            return True
        elif kind == "cancel":
            self._pressed = None
        elif kind == "up" and self._pressed:
            name, self._pressed = self._pressed, None
            rect = self.save_rect if name == "save" else self.clear_rect
            if rect.collidepoint(pos):
                self.save_as_playlist() if name == "save" else self.clear()
            self.dirty = True
            return True
        if self.items and self.list_rect.collidepoint(pos) or kind in ("move", "up", "cancel"):
            r = self.list.handle_touch(pos, kind)
            if r:
                self.dirty = True
            return r
        return False

    # ---- draw ----------------------------------------------------------------
    def _draw_row(self, surface, rect, item, index, state):
        cur = index == self.current_index
        if cur:
            pygame.draw.rect(surface, theme.BG_LIGHT, rect)
            pygame.draw.rect(surface, theme.PRIMARY, (rect.left, rect.top, 4, rect.h))
        num = text_cache.render(str(index + 1), theme.FS_SMALL, theme.PRIMARY_LIGHT if cur else theme.TEXT_DISABLED)
        surface.blit(num, num.get_rect(midleft=(rect.left + 8, rect.centery)))
        tx = rect.left + 40
        tw = rect.w - 40 - X_ZONE
        t = text_cache.render(text_cache.ellipsize(track_title(item), theme.FS_BODY, tw), theme.FS_BODY,
                              theme.PRIMARY_LIGHT if cur else theme.TEXT)
        a = text_cache.render(text_cache.ellipsize(track_artist(item), theme.FS_SMALL, tw), theme.FS_SMALL, theme.TEXT_DIM)
        surface.blit(t, (tx, rect.top + 10))
        surface.blit(a, (tx, rect.top + 32))
        x = text_cache.render("x", theme.FS_TITLE, theme.TEXT_DIM)
        surface.blit(x, x.get_rect(center=(rect.right - X_ZONE // 2, rect.centery)))
        pygame.draw.line(surface, theme.BORDER, (rect.left, rect.bottom - 1), (rect.right, rect.bottom - 1))

    def draw(self, surface):
        surface.fill(theme.BG, (0, theme.CONTENT_TOP, theme.SCREEN_W, theme.CONTENT_BOTTOM_MINI - theme.CONTENT_TOP))
        n = len(self.items)
        head = text_cache.render("Queue" if not n else "Queue (%d)" % n, theme.FS_TITLE, theme.TEXT, True)
        surface.blit(head, head.get_rect(midleft=(theme.PAD, theme.CONTENT_TOP + HEADER_H // 2)))
        for name, rect, label in (("save", self.save_rect, "Save"), ("clear", self.clear_rect, "Clear")):
            on = n > 0
            bg = theme.BG_PRESSED if self._pressed == name else theme.BG_LIGHT
            pygame.draw.rect(surface, bg, rect, border_radius=8)
            s = text_cache.render(label, theme.FS_BODY, theme.TEXT if on else theme.TEXT_DISABLED)
            surface.blit(s, s.get_rect(center=rect.center))
        if not n:
            for i, (txt, col) in enumerate((("Queue is empty", theme.TEXT_DIM),
                                            ("Add songs from Library", theme.TEXT_DISABLED))):
                s = text_cache.render(txt, theme.FS_BODY, col)
                surface.blit(s, s.get_rect(center=(theme.SCREEN_W // 2, self.list_rect.centery - 10 + i * 24)))
        else:
            self.list.draw(surface)
        self.dirty = False

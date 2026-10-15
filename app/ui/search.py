"""Search: query box + on-screen keyboard, chips All/Songs/Artists/Albums."""
import pygame

from ui import theme
from ui import text_cache
from ui.keyboard import Keyboard
from ui.widgets import Button, ScrollList
from ui.songs import (BrowseScreen, LIST_TOP, HEADER_H, draw_track_row, play_tracks,
                      track_actions)
from ui.artists import plural

CHIPS = [("all", "All"), ("songs", "Songs"), ("artists", "Artists"), ("albums", "Albums")]
CHIP_H = theme.MIN_TOUCH
CHIPS_Y = LIST_TOP
KB_H = 194
KB_Y = theme.CONTENT_BOTTOM - KB_H
MAX_ALL = 5   # per section in the "All" chip


class SearchScreen(BrowseScreen):
    title = "Search"
    has_mini_player = False   # keyboard needs the full content area

    def __init__(self, screen_manager, audio_player, music_library, playlist_store=None):
        super().__init__(screen_manager, audio_player, music_library, playlist_store)
        self.query = ""
        self.kind = "all"
        self.songs = []
        self.rows = []
        self.keyboard_open = True
        cw = theme.SCREEN_W // len(CHIPS)
        self.chips = []
        for i, (k, label) in enumerate(CHIPS):
            self.chips.append((k, Button((i * cw, CHIPS_Y, cw, CHIP_H), label,
                                         lambda k=k: self.set_kind(k), style="primary" if k == self.kind else "secondary")))
        self.field = pygame.Rect(70, theme.CONTENT_TOP + 5, theme.SCREEN_W - 70 - theme.PAD, HEADER_H - 10)
        self.keyboard = Keyboard((0, KB_Y, theme.SCREEN_W, KB_H), self.on_key,
                                 self.close_keyboard, self.close_keyboard)
        self.list = ScrollList(self._list_rect(), theme.ROW_H, self._draw_row,
                               self._on_tap, self._on_long)
        self.lists.append(self.list)
        self._sync_widgets()

    # --- layout
    def _list_rect(self):
        top = CHIPS_Y + CHIP_H
        bottom = KB_Y if self.keyboard_open else theme.CONTENT_BOTTOM
        return pygame.Rect(0, top, theme.SCREEN_W, bottom - top)

    def _sync_widgets(self):
        self.list.rect = self._list_rect()
        self.widgets = ([self.keyboard] if self.keyboard_open else []) + \
                       [b for _, b in self.chips] + [self.list]
        self.dirty = True

    def on_enter(self, **kw):
        self.keyboard_open = True
        self._sync_widgets()
        super().on_enter(**kw)

    def close_keyboard(self):
        self.keyboard_open = False
        self._sync_widgets()

    def open_keyboard(self):
        self.keyboard_open = True
        self._sync_widgets()

    # --- input
    def on_key(self, key):
        k = key if isinstance(key, str) else str(key)
        low = k.lower()
        if low in ("backspace", "bksp", "\b", "<-", "del", "delete"):
            self.query = self.query[:-1]
        elif low in ("space", " "):
            self.query += " "
        elif low in ("clear",):
            self.query = ""
        elif len(k) == 1 and k.isprintable():
            self.query += k
        else:
            return
        self.run_search()

    def set_kind(self, kind):
        self.kind = kind
        for k, b in self.chips:
            b.style = "primary" if k == kind else "secondary"
        self.run_search()

    def run_search(self):
        q = self.query.strip()
        self.rows, self.songs = [], []
        if q:
            res = self.music_library.search(q, self.kind) or {}
            self.songs = list(res.get("songs") or [])
            artists = list(res.get("artists") or [])
            albums = list(res.get("albums") or [])
            show_all = self.kind == "all"
            cap = (lambda l: l[:MAX_ALL]) if show_all else (lambda l: l)
            if self.kind in ("all", "songs") and self.songs:
                if show_all:
                    self.rows.append({"kind": "header", "label": "Songs"})
                # song rows keep their index within self.songs so queue == results
                for i, t in enumerate(cap(self.songs)):
                    self.rows.append({"kind": "song", "track": t, "index": i})
            if self.kind in ("all", "artists") and artists:
                if show_all:
                    self.rows.append({"kind": "header", "label": "Artists"})
                self.rows.extend({"kind": "artist", "artist": a} for a in cap(artists))
            if self.kind in ("all", "albums") and albums:
                if show_all:
                    self.rows.append({"kind": "header", "label": "Albums"})
                self.rows.extend({"kind": "album", "album": a} for a in cap(albums))
        self.list.set_items(self.rows)
        self.list.scroll_to_index(0) if self.rows else None
        self.dirty = True

    def handle_touch(self, pos, kind):
        if kind == "down" and self.field.collidepoint(pos) and not self.keyboard_open:
            self.open_keyboard()
            return True
        return super().handle_touch(pos, kind)

    # --- list callbacks
    def _draw_row(self, surface, rect, item, index, state):
        k = item["kind"]
        x = rect.x + theme.PAD
        if k == "header":
            surface.blit(text_cache.render(item["label"].upper(), theme.FS_SMALL, theme.PRIMARY_LIGHT),
                         (x, rect.centery - 7))
            return
        if k == "song":
            t = item["track"]
            draw_track_row(surface, rect, t, t.get("id") == self.current_id, self.thumbs.get(t))
            return
        if k == "artist":
            a = item["artist"]
            name, sub = a.get("name") or "Unknown", plural(a.get("track_count", 0), "song")
        else:
            a = item["album"]
            name, sub = a.get("title") or "Unknown", a.get("artist") or ""
        w = rect.w - 2 * theme.PAD
        surface.blit(text_cache.render(text_cache.ellipsize(name, theme.FS_BODY, w), theme.FS_BODY, theme.TEXT), (x, rect.y + 9))
        surface.blit(text_cache.render(text_cache.ellipsize(sub, theme.FS_SMALL, w), theme.FS_SMALL, theme.TEXT_DIM), (x, rect.y + 31))
        pygame.draw.line(surface, theme.BORDER, (x, rect.bottom - 1), (rect.right, rect.bottom - 1))

    def _on_tap(self, item, index):
        k = item["kind"]
        if k == "song":
            play_tracks(self.audio_player, self.songs, item["index"])
        elif k == "artist":
            self.screen_manager.push("artist_detail", artist_name=item["artist"].get("name"))
        elif k == "album":
            a = item["album"]
            self.screen_manager.push("album_detail", title=a.get("title"), artist=a.get("artist"))

    def _on_long(self, item, index):
        if item["kind"] == "song":
            track_actions(self.screen_manager, self.audio_player, self.store, item["track"])

    # --- draw
    def draw(self, surface):
        self.draw_header(surface, "")
        pygame.draw.rect(surface, theme.BG_LIGHT, self.field, border_radius=6)
        shown = self.query or "Search music"
        color = theme.TEXT if self.query else theme.TEXT_DISABLED
        txt = text_cache.ellipsize(shown + ("|" if self.keyboard_open and self.query else ""),
                                   theme.FS_BODY, self.field.w - 16)
        s = text_cache.render(txt, theme.FS_BODY, color)
        surface.blit(s, (self.field.x + 8, self.field.centery - s.get_height() // 2))
        for _, b in self.chips:
            b.draw(surface)
        if self.query.strip() and not self.rows:
            m = text_cache.render("No results", theme.FS_BODY, theme.TEXT_DIM)
            surface.blit(m, m.get_rect(center=(theme.SCREEN_W // 2, self.list.rect.centery)))
        else:
            self.list.draw(surface)
        if self.keyboard_open:
            self.keyboard.draw(surface)

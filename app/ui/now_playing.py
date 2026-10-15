"""Now Playing screen: art, marquee title, seek bar, transport controls.

Layout (320x480, no mini-player here; the tab bar owns y>=424):
  art 200x200 @ y=32, title marquee, artist, album, seek zone (44 px tall hit
  area, bar drawn in its middle), time labels, then shuffle/prev/play/next/repeat.

Seek commits on release only (a drag just moves the thumb and a time bubble),
state is polled from AudioPlayer.get_state() at <= 5 Hz, and album art is
fetched on a worker thread into a small LRU so draw() never blocks.
"""
import os
import queue as _queue
import threading
from collections import OrderedDict

import pygame

from ui import theme, text_cache
from ui.screen_manager import Screen
from ui.widgets import Marquee

POLL_S = 0.2           # 5 Hz
ART_SIZE = 200
ART_CACHE_MAX = 6
_TILE_COLORS = [(138, 43, 226), (41, 128, 185), (39, 174, 96), (211, 84, 0),
                (192, 57, 43), (22, 160, 133), (142, 68, 173), (44, 62, 80)]


def fmt_time(seconds):
    s = int(seconds or 0)
    if s < 0:
        s = 0
    return "%d:%02d" % (s // 60, s % 60)


def track_title(track):
    if not track:
        return ""
    t = track.get("title")
    if t:
        return str(t)
    p = track.get("path") or ""
    return os.path.splitext(os.path.basename(p))[0] or "Unknown title"


def track_artist(track):
    return (track or {}).get("artist") or "Unknown Artist"


def letter_tile(track, size):
    """Placeholder art: coloured square with the title's first letter."""
    key = (track.get("album") or track.get("title") or track.get("id") or "?") if track else "?"
    color = _TILE_COLORS[sum(ord(c) for c in str(key)) % len(_TILE_COLORS)]
    s = pygame.Surface((size, size))
    s.fill(color)
    title = track_title(track)
    ch = (title[:1] or "?").upper()
    glyph = text_cache.render(ch, max(24, size // 2), (255, 255, 255), True)
    s.blit(glyph, glyph.get_rect(center=(size // 2, size // 2)))
    return s


def draw_icon(surface, name, rect, color):
    """Small vector transport icons (no font/asset dependency)."""
    cx, cy = rect.center
    u = min(rect.w, rect.h) // 4        # icon unit
    if name == "play":
        pygame.draw.polygon(surface, color, [(cx - u + 2, cy - u - 2), (cx - u + 2, cy + u + 2), (cx + u + 3, cy)])
    elif name == "pause":
        pygame.draw.rect(surface, color, (cx - u, cy - u - 2, u - 1, 2 * u + 4))
        pygame.draw.rect(surface, color, (cx + 2, cy - u - 2, u - 1, 2 * u + 4))
    elif name == "next":
        pygame.draw.polygon(surface, color, [(cx - u, cy - u), (cx - u, cy + u), (cx + u - 3, cy)])
        pygame.draw.rect(surface, color, (cx + u - 1, cy - u, 3, 2 * u))
    elif name == "prev":
        pygame.draw.polygon(surface, color, [(cx + u, cy - u), (cx + u, cy + u), (cx - u + 3, cy)])
        pygame.draw.rect(surface, color, (cx - u - 2, cy - u, 3, 2 * u))
    elif name == "shuffle":
        pygame.draw.lines(surface, color, False, [(cx - u - 3, cy + u - 2), (cx - 2, cy + u - 2), (cx + 2, cy - u + 2), (cx + u, cy - u + 2)], 2)
        pygame.draw.lines(surface, color, False, [(cx - u - 3, cy - u + 2), (cx - 2, cy - u + 2), (cx + 2, cy + u - 2), (cx + u, cy + u - 2)], 2)
        pygame.draw.polygon(surface, color, [(cx + u, cy - u - 2), (cx + u + 5, cy - u + 2), (cx + u, cy - u + 6)])
        pygame.draw.polygon(surface, color, [(cx + u, cy + u - 6), (cx + u + 5, cy + u - 2), (cx + u, cy + u + 2)])
    elif name in ("repeat", "repeat_one"):
        pygame.draw.rect(surface, color, (cx - u - 2, cy - u + 1, 2 * u + 5, 2 * u - 2), 2, border_radius=4)
        pygame.draw.polygon(surface, theme.BG, [(cx - 2, cy - u - 3), (cx + 6, cy - u - 3), (cx + 6, cy - u + 5)])
        pygame.draw.polygon(surface, color, [(cx + 6, cy - u - 3), (cx + 6, cy - u + 5), (cx + 11, cy - u + 1)])
        if name == "repeat_one":
            t = text_cache.render("1", theme.FS_SMALL, color, True)
            surface.blit(t, t.get_rect(center=(cx + 1, cy)))


class NowPlayingScreen(Screen):
    has_mini_player = False

    def __init__(self, screen_manager, audio_player, music_library=None):
        super().__init__(screen_manager)
        self.audio = audio_player
        self.library = music_library

        w = theme.SCREEN_W
        self.art_rect = pygame.Rect((w - ART_SIZE) // 2, 32, ART_SIZE, ART_SIZE)
        self.title_rect = pygame.Rect(theme.PAD, 240, w - 2 * theme.PAD, 26)
        self.artist_rect = pygame.Rect(theme.PAD, 268, w - 2 * theme.PAD, 20)
        self.album_rect = pygame.Rect(theme.PAD, 288, w - 2 * theme.PAD, 16)
        self.seek_rect = pygame.Rect(20, 308, w - 40, theme.MIN_TOUCH)       # hit zone 44 px
        self.time_y = 352
        by, bh, bw = 372, 48, 56
        centers = (36, 98, 160, 222, 284)
        r = lambda cx: pygame.Rect(cx - bw // 2, by, bw, bh)
        (self.shuffle_rect, self.prev_rect, self.play_rect,
         self.next_rect, self.repeat_rect) = [r(c) for c in centers]
        self._buttons = {"shuffle": self.shuffle_rect, "prev": self.prev_rect,
                         "play": self.play_rect, "next": self.next_rect,
                         "repeat": self.repeat_rect}

        self.title_marquee = Marquee(self.title_rect, "Nothing playing", theme.FS_TITLE, theme.TEXT, True)
        self.title_text = "Nothing playing"
        self.artist_text = "Pick a song from Library"
        self.album_text = ""
        self._title_scrolls = False
        self._placeholder = None

        self.state = {}
        self.track = None
        self.playing = False
        self.position = 0.0
        self.duration = 0.0
        self.shuffle = False
        self.repeat = "off"
        self._poll_acc = POLL_S        # poll on first update
        self._last_sec = -1
        self._last_total = -1
        self.time_renders = 0
        self.pos_text = "0:00"
        self.dur_text = "0:00"

        self.seek_dragging = False
        self.seek_value = 0.0
        self._pressed = None

        # art
        self.art_surface = None
        self._art_key = None
        self._art_cache = OrderedDict()
        self._art_lock = threading.Lock()
        self._art_jobs = _queue.Queue()
        self._art_done = {}
        self._art_pending = set()
        self._worker = None
        self._refresh()

    # ---- lifecycle -------------------------------------------------------
    def on_enter(self, **kw):
        self._poll_acc = 0.0
        self._pressed = None
        self.seek_dragging = False
        self._refresh()
        self.dirty = True

    def on_leave(self):
        self._pressed = None
        self.seek_dragging = False

    # ---- state -----------------------------------------------------------
    def _refresh(self):
        try:
            st = self.audio.get_state() or {}
        except Exception:
            st = {}
        track = st.get("track")
        changed = False
        if (track or {}).get("id") != (self.track or {}).get("id") or (track is None) != (self.track is None):
            self.track = track
            self._apply_track()
            changed = True
        for attr, key, default in (("playing", "playing", False), ("shuffle", "shuffle", False),
                                   ("repeat", "repeat", "off")):
            v = st.get(key, default)
            if getattr(self, attr) != v:
                setattr(self, attr, v)
                changed = True
        self.position = float(st.get("position") or 0.0)
        self.duration = float((track or {}).get("duration") or st.get("duration") or 0.0) if track else 0.0
        if self.duration <= 0 and track:
            self.duration = float(st.get("duration") or 0.0)
        sec, tot = int(self.position), int(self.duration)
        if sec != self._last_sec or tot != self._last_total:
            self._last_sec, self._last_total = sec, tot
            self.pos_text, self.dur_text = fmt_time(sec), fmt_time(tot)
            self.time_renders += 1
            changed = True
        if not self.seek_dragging and self.duration > 0:
            v = min(1.0, max(0.0, self.position / self.duration))
            if abs(v - self.seek_value) > 0.002:
                self.seek_value = v
                changed = True
        elif self.duration <= 0 and self.seek_value:
            self.seek_value = 0.0
            changed = True
        if changed:
            self.dirty = True

    def _apply_track(self):
        t = self.track
        if t:
            self.title_text = track_title(t)
            self.artist_text = track_artist(t)
            self.album_text = t.get("album") or ""
        else:
            self.title_text = "Nothing playing"
            self.artist_text = "Pick a song from Library"
            self.album_text = ""
        self.title_marquee.set_text(self.title_text)
        self._title_scrolls = text_cache.text_width(self.title_text, theme.FS_TITLE, True) > self.title_rect.w
        self._placeholder = letter_tile(t, ART_SIZE) if t else None
        self._load_art()

    # ---- art (async + LRU) ----------------------------------------------
    def _load_art(self):
        t = self.track
        if not t:
            self.art_surface, self._art_key = None, None
            return
        key = t.get("id") or t.get("path")
        self._art_key = key
        if key in self._art_cache:
            self._art_cache.move_to_end(key)
            self.art_surface = self._art_cache[key]
            return
        self.art_surface = None
        if self.library is None or not hasattr(self.library, "get_art"):
            self._store_art(key, letter_tile(t, ART_SIZE))
            return
        with self._art_lock:
            if key in self._art_pending:
                return
            self._art_pending.add(key)
        self._art_jobs.put((key, t))
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._art_worker, daemon=True)
            self._worker.start()

    def _art_worker(self):
        while True:
            try:
                key, t = self._art_jobs.get(timeout=2.0)
            except _queue.Empty:
                return
            try:
                art = self.library.get_art(t, ART_SIZE)
            except Exception:
                art = None
            with self._art_lock:
                self._art_done[key] = (art, t)

    def _store_art(self, key, surf):
        self._art_cache[key] = surf
        self._art_cache.move_to_end(key)
        while len(self._art_cache) > ART_CACHE_MAX:
            self._art_cache.popitem(last=False)
        if key == self._art_key:
            self.art_surface = surf
            self.dirty = True

    def _collect_art(self):
        if not self._art_done:
            return
        with self._art_lock:
            done, self._art_done = self._art_done, {}
            for k in done:
                self._art_pending.discard(k)
        for key, (art, t) in done.items():
            if art is not None and art.get_size() != (ART_SIZE, ART_SIZE):
                try:
                    art = pygame.transform.smoothscale(art, (ART_SIZE, ART_SIZE))
                except Exception:
                    art = None
            self._store_art(key, art if art is not None else letter_tile(t, ART_SIZE))

    # ---- update ----------------------------------------------------------
    def update(self, dt):
        self._poll_acc += dt
        if self._poll_acc >= POLL_S:
            self._poll_acc = 0.0
            self._refresh()
        self._collect_art()
        self.title_marquee.update(dt)
        if self._title_scrolls:
            self.dirty = True

    # ---- touch -----------------------------------------------------------
    def _seek_frac(self, x):
        bar = self.seek_rect
        return min(1.0, max(0.0, (x - bar.left) / float(bar.w)))

    def handle_touch(self, pos, kind):
        if kind == "cancel":
            self._pressed = None
            if self.seek_dragging:
                self.seek_dragging = False
                self.dirty = True
            return True
        if kind == "down":
            if self.track is not None and self.seek_rect.collidepoint(pos):
                self.seek_dragging = True
                self.seek_value = self._seek_frac(pos[0])
                self.dirty = True
                return True
            for name, rect in self._buttons.items():
                if rect.collidepoint(pos):
                    self._pressed = name
                    self.dirty = True
                    return True
            return False
        if kind == "move":
            if self.seek_dragging:
                self.seek_value = self._seek_frac(pos[0])
                self.dirty = True
                return True
            if self._pressed and not self._buttons[self._pressed].collidepoint(pos):
                self._pressed = None          # drag-out cancels
                self.dirty = True
            return self._pressed is not None
        if kind == "up":
            if self.seek_dragging:
                self.seek_dragging = False
                self.seek_value = self._seek_frac(pos[0])
                self.audio.seek(self.seek_value)
                self.dirty = True
                return True
            name, self._pressed = self._pressed, None
            if name and self._buttons[name].collidepoint(pos):
                self._activate(name)
                self.dirty = True
                return True
            self.dirty = True
        return False

    def _activate(self, name):
        if name == "play":
            if self.track is not None:
                self.audio.toggle()
        elif name == "next":
            if self.track is not None:
                self.audio.next()
        elif name == "prev":
            if self.track is not None:
                self.audio.prev()
        elif name == "shuffle":
            self.audio.shuffle = not bool(self.audio.shuffle)
            self.shuffle = self.audio.shuffle
        elif name == "repeat":
            order = ["off", "all", "one"]
            cur = self.audio.repeat if self.audio.repeat in order else "off"
            self.audio.repeat = order[(order.index(cur) + 1) % 3]
            self.repeat = self.audio.repeat

    # ---- draw ------------------------------------------------------------
    def draw(self, surface):
        surface.fill(theme.BG, (0, theme.STATUS_H, theme.SCREEN_W, theme.TAB_Y - theme.STATUS_H))
        art = (self.art_surface or self._placeholder) if self.track else None
        if art is not None:
            surface.blit(art, self.art_rect)
        else:
            pygame.draw.rect(surface, theme.BG_LIGHT, self.art_rect, border_radius=8)
            note = text_cache.render("♪" if False else "No music", theme.FS_BODY, theme.TEXT_DIM)
            surface.blit(note, note.get_rect(center=self.art_rect.center))
        pygame.draw.rect(surface, theme.BORDER, self.art_rect, 1)

        self.title_marquee.draw(surface)
        self._blit_centered(surface, self.artist_text, theme.FS_BODY, theme.TEXT_DIM, self.artist_rect)
        if self.album_text:
            self._blit_centered(surface, self.album_text, theme.FS_SMALL, theme.TEXT_DISABLED, self.album_rect)

        self._draw_seek(surface)
        self._draw_controls(surface)
        self.dirty = False

    def _blit_centered(self, surface, text, size, color, rect):
        s = text_cache.render(text_cache.ellipsize(text, size, rect.w), size, color)
        surface.blit(s, s.get_rect(center=rect.center))

    def _draw_seek(self, surface):
        bar = self.seek_rect
        y = bar.centery
        track_r = pygame.Rect(bar.left, y - 2, bar.w, 4)
        pygame.draw.rect(surface, theme.BG_PRESSED, track_r, border_radius=2)
        fill = int(bar.w * self.seek_value)
        if fill > 0:
            pygame.draw.rect(surface, theme.PRIMARY, (bar.left, y - 2, fill, 4), border_radius=2)
        pygame.draw.circle(surface, theme.TEXT, (bar.left + fill, y), 8 if self.seek_dragging else 6)
        if self.seek_dragging and self.duration > 0:
            bubble = text_cache.render(fmt_time(self.seek_value * self.duration), theme.FS_BODY, theme.TEXT)
            br = bubble.get_rect(center=(min(max(bar.left + fill, bar.left + 24), bar.right - 24), bar.top + 2))
            pygame.draw.rect(surface, theme.PRIMARY_DARK, br.inflate(10, 4), border_radius=4)
            surface.blit(bubble, br)
        left = text_cache.render(self.pos_text, theme.FS_SMALL, theme.TEXT_DIM)
        right = text_cache.render(self.dur_text, theme.FS_SMALL, theme.TEXT_DIM)
        surface.blit(left, (bar.left, self.time_y))
        surface.blit(right, (bar.right - right.get_width(), self.time_y))

    def _draw_controls(self, surface):
        enabled = self.track is not None
        for name, rect in self._buttons.items():
            pressed = self._pressed == name
            if name == "play":
                col = theme.PRIMARY_DARK if pressed else (theme.PRIMARY if enabled else theme.BG_LIGHT)
                pygame.draw.circle(surface, col, rect.center, 24)
                draw_icon(surface, "pause" if self.playing else "play", rect, theme.TEXT if enabled else theme.TEXT_DISABLED)
                continue
            if pressed:
                pygame.draw.rect(surface, theme.BG_PRESSED, rect, border_radius=8)
            if name == "shuffle":
                color, icon = (theme.PRIMARY_LIGHT if self.shuffle else theme.TEXT_DIM), "shuffle"
            elif name == "repeat":
                color = theme.PRIMARY_LIGHT if self.repeat != "off" else theme.TEXT_DIM
                icon = "repeat_one" if self.repeat == "one" else "repeat"
            else:
                color, icon = (theme.TEXT if enabled else theme.TEXT_DISABLED), name
            draw_icon(surface, icon, rect, color)

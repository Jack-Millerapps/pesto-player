"""Songs screen plus helpers shared by the other browse screens.

Shared here (not in a separate module) because this task owns only the
browse files: BrowseScreen base, track_row drawing, play helpers, the
long-press action sheet and the empty-state widget.
"""
import collections
import queue as _queue
import random
import threading

import pygame

from ui import theme
from ui import text_cache
from ui.screen_manager import Screen
from ui.widgets import Button, ScrollList

HEADER_H = 44
LIST_TOP = theme.CONTENT_TOP + HEADER_H          # 68
LIST_BOTTOM = theme.CONTENT_BOTTOM_MINI          # 376 (mini-player is shown)
THUMB = 40
RAIL_W = 20
RAIL_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ#"


# ----------------------------------------------------------------- helpers
def track_title(track):
    t = (track.get("title") or "").strip()
    if t:
        return t
    path = track.get("path") or ""
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[0] if name else "Unknown"


def track_sub(track):
    parts = [p for p in ((track.get("artist") or "").strip(),
                         (track.get("album") or "").strip()) if p]
    return " - ".join(parts)


def play_tracks(audio_player, tracks, index=0, shuffle=None):
    """Replace the queue with `tracks` starting at `index`, then play."""
    if not tracks:
        return
    if shuffle is not None:
        audio_player.shuffle = shuffle
    audio_player.set_queue(list(tracks), index)   # set_queue starts playback itself


def shuffle_start_index(tracks):
    return random.randrange(len(tracks)) if tracks else 0


def get_store(playlist_store):
    if playlist_store is not None:
        return playlist_store
    from player.playlist import PlaylistStore
    return PlaylistStore()


def next_playlist_name(store):
    names = set(store.list_names())
    n = 1
    while f"Playlist {n}" in names:
        n += 1
    return f"Playlist {n}"


def track_actions(sm, audio_player, store, track, extra=None):
    """Open the long-press action sheet for one track."""
    def play_next():
        audio_player.play_next(track)
        sm.toast("Playing next")

    def enqueue():
        audio_player.enqueue(track)
        sm.toast("Added to queue")

    def add_to_playlist():
        names = store.list_names()
        actions = []
        for name in names:
            actions.append((name, lambda n=name: _add(n)))
        actions.append(("New playlist", lambda: _add(next_playlist_name(store))))
        sm.show_sheet(actions)

    def _add(name):
        if name in store.list_names():
            store.add(name, track)
        else:
            store.save(name, [track])
        sm.toast(f"Added to {name}")

    actions = [("Play next", play_next), ("Add to queue", enqueue),
               ("Add to playlist", add_to_playlist)]
    if extra:
        actions.extend(extra)
    sm.show_sheet(actions)


def draw_track_row(surface, rect, track, current, thumb=None):
    """Standard 56 px track row: thumbnail, title, 'artist - album'."""
    x = rect.x + theme.PAD
    cy = rect.centery
    if thumb is not None:
        surface.blit(thumb, (x, cy - thumb.get_height() // 2))
    else:
        tile = pygame.Rect(x, cy - THUMB // 2, THUMB, THUMB)
        pygame.draw.rect(surface, theme.BG_PRESSED, tile, border_radius=4)
        letter = track_title(track)[:1].upper() or "?"
        ls = text_cache.render(letter, theme.FS_TITLE, theme.TEXT_DIM)
        surface.blit(ls, ls.get_rect(center=tile.center))
    tx = x + THUMB + 10
    max_w = rect.right - theme.PAD - tx - (14 if current else 0)
    color = theme.PRIMARY_LIGHT if current else theme.TEXT
    title = text_cache.ellipsize(track_title(track), theme.FS_BODY, max_w)
    surface.blit(text_cache.render(title, theme.FS_BODY, color), (tx, rect.y + 9))
    sub = text_cache.ellipsize(track_sub(track), theme.FS_SMALL, max_w)
    surface.blit(text_cache.render(sub, theme.FS_SMALL, theme.TEXT_DIM), (tx, rect.y + 31))
    if current:
        cx = rect.right - theme.PAD - 4
        pygame.draw.polygon(surface, theme.PRIMARY_LIGHT,
                            [(cx - 4, cy - 6), (cx - 4, cy + 6), (cx + 4, cy)])
    pygame.draw.line(surface, theme.BORDER, (rect.x + theme.PAD, rect.bottom - 1),
                     (rect.right, rect.bottom - 1))


class ArtLoader:
    """Worker-thread art loader with a small shared LRU. draw() never decodes.

    request(key, fn) returns the cached Surface (or None while loading / if
    there is no art); fn runs on the worker. `version` bumps when something
    finishes so screens know to redraw.
    """
    MAX = 96

    def __init__(self):
        self._lock = threading.Lock()
        self._cache = collections.OrderedDict()
        self._pending = set()
        self._jobs = _queue.Queue()
        self._thread = None
        self.version = 0

    def request(self, key, fn):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            if key not in self._pending:
                self._pending.add(key)
                self._jobs.put((key, fn))
                if self._thread is None:
                    self._thread = threading.Thread(target=self._work, daemon=True)
                    self._thread.start()
        return None

    def _work(self):
        while True:
            key, fn = self._jobs.get()
            try:
                surf = fn()
            except Exception:
                surf = None
            with self._lock:
                self._pending.discard(key)
                self._cache[key] = surf
                while len(self._cache) > self.MAX:
                    self._cache.popitem(last=False)
                self.version += 1

    def wait_idle(self, timeout=2.0):
        """Test helper: block until no jobs are pending."""
        import time
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self._lock:
                if not self._pending:
                    return True
            time.sleep(0.005)
        return False


_loaders = {}


def loader_for(library):
    ld = _loaders.get(id(library))
    if ld is None:
        ld = _loaders[id(library)] = ArtLoader()
    return ld


class ThumbCache:
    """Per-library thumbnail access through the shared async loader."""

    def __init__(self, library):
        self.library = library
        self.loader = loader_for(library)

    def get(self, track):
        lib = self.library
        return self.loader.request((track.get("id"), THUMB),
                                   lambda: lib.get_art(track, THUMB))


class EmptyState:
    """Centered message plus an 'Add music' button."""

    def __init__(self, rect, message, on_add):
        self.rect = pygame.Rect(rect)
        self.message = message
        self.button = Button((rect[0] + (rect[2] - 160) // 2, rect[1] + rect[3] // 2 + 10,
                              160, theme.MIN_TOUCH), "Add music", on_add) if on_add else None

    def handle_touch(self, pos, kind):
        return self.button.handle_touch(pos, kind) if self.button else False

    def draw(self, surface):
        s = text_cache.render(self.message, theme.FS_BODY, theme.TEXT_DIM)
        surface.blit(s, s.get_rect(center=(self.rect.centerx, self.rect.centery - 16)))
        if self.button:
            self.button.draw(surface)


# -------------------------------------------------------------- base class
class BrowseScreen(Screen):
    """Header (optional back button + title), touch routing, dirty tracking."""
    title = ""
    has_back = True

    def __init__(self, screen_manager, audio_player, music_library, playlist_store=None):
        super().__init__(screen_manager)
        self.audio_player = audio_player
        self.music_library = music_library
        self._store = playlist_store
        self.thumbs = ThumbCache(music_library)
        self.current_id = None
        self._poll = 0.0
        self._was_scanning = False
        self._art_seen = self.thumbs.loader.version
        self.header_buttons = []
        self.back_button = None
        if self.has_back:
            self.back_button = Button((0, theme.CONTENT_TOP, 64, HEADER_H), "Back",
                                      self._on_back, style="secondary")
            self.header_buttons.append(self.back_button)
        self.widgets = []       # things with handle_touch, tried in order
        self.lists = []         # ScrollLists to update()

    @property
    def store(self):
        if self._store is None:
            self._store = get_store(None)
        return self._store

    def _on_back(self):
        if self.screen_manager:
            self.screen_manager.pop()

    def _go_add_music(self):
        if self.screen_manager:
            self.screen_manager.push("add_music")

    # state polling (current-track marker), <= 4 Hz
    def _poll_current(self):
        try:
            tr = self.audio_player.get_state().get("track")
        except Exception:
            tr = None
        cid = tr.get("id") if tr else None
        if cid != self.current_id:
            self.current_id = cid
            self.dirty = True

    def update(self, dt):
        self._poll += dt
        if self._poll >= 0.25:
            self._poll = 0.0
            self._poll_current()
        try:
            scanning = bool(self.music_library.is_scanning())
        except Exception:
            scanning = False
        if self._was_scanning and not scanning:
            self.on_scan_done()
        self._was_scanning = scanning
        if self.thumbs.loader.version != self._art_seen:
            self._art_seen = self.thumbs.loader.version
            self.dirty = True
        for lst in self.lists:
            lst.update(dt)
            if lst.dirty:
                self.dirty = True

    def handle_touch(self, pos, kind):
        handled = False
        for b in self.header_buttons:
            if b.handle_touch(pos, kind):
                handled = True
        if not handled:
            for w in self.widgets:
                if w.handle_touch(pos, kind):
                    handled = True
                    break
        self.dirty = True
        return handled or True

    def on_scan_done(self):
        if hasattr(self, "reload"):
            self.reload()
        self.dirty = True

    def on_enter(self, **kw):
        self._poll_current()
        self.dirty = True

    def draw_header(self, surface, title=None):
        surface.fill(theme.BG)
        pygame.draw.rect(surface, theme.BG_DARK,
                         (0, theme.CONTENT_TOP, theme.SCREEN_W, HEADER_H))
        for b in self.header_buttons:
            b.draw(surface)
        left = 70 if self.has_back else theme.PAD
        right = theme.SCREEN_W - theme.PAD - sum(b.rect.w + 6 for b in self.header_buttons
                                                 if b is not self.back_button)
        t = text_cache.ellipsize(title if title is not None else self.title,
                                 theme.FS_TITLE, right - left, bold=True)
        s = text_cache.render(t, theme.FS_TITLE, theme.TEXT, bold=True)
        surface.blit(s, (left, theme.CONTENT_TOP + (HEADER_H - s.get_height()) // 2))
        pygame.draw.line(surface, theme.BORDER, (0, LIST_TOP - 1), (theme.SCREEN_W, LIST_TOP - 1))


# ------------------------------------------------------------ Songs screen
class SongsScreen(BrowseScreen):
    title = "Songs"

    def __init__(self, screen_manager, audio_player, music_library, playlist_store=None):
        super().__init__(screen_manager, audio_player, music_library, playlist_store)
        self.tracks = []
        self.list = ScrollList((0, LIST_TOP, theme.SCREEN_W - RAIL_W, LIST_BOTTOM - LIST_TOP),
                               theme.ROW_H, self._draw_row, self._on_tap, self._on_long)
        self.lists.append(self.list)
        self.rail = pygame.Rect(theme.SCREEN_W - RAIL_W, LIST_TOP, RAIL_W, LIST_BOTTOM - LIST_TOP)
        self.empty = EmptyState((0, LIST_TOP, theme.SCREEN_W, LIST_BOTTOM - LIST_TOP),
                                "No songs yet", self._go_add_music)
        self.reload()

    def reload(self):
        self.tracks = list(self.music_library.get_tracks())
        self.list.set_items(self.tracks)
        self.widgets = [self.list] if self.tracks else [self.empty]
        self.dirty = True

    def on_enter(self, **kw):
        self.reload()
        super().on_enter(**kw)

    # --- callbacks
    def _draw_row(self, surface, rect, item, index, state):
        draw_track_row(surface, rect, item, item.get("id") == self.current_id,
                       self.thumbs.get(item))

    def _on_tap(self, item, index):
        play_tracks(self.audio_player, self.tracks, index)

    def _on_long(self, item, index):
        track_actions(self.screen_manager, self.audio_player, self.store, item)

    # --- alphabet rail
    @staticmethod
    def _letter_of(track):
        c = track_title(track)[:1].upper()
        return c if "A" <= c <= "Z" else "#"

    def index_for_letter(self, letter):
        """First track at or after `letter` ('#' = non-alpha, sorted first or last)."""
        if letter == "#":
            for i, t in enumerate(self.tracks):
                if self._letter_of(t) == "#":
                    return i
            return len(self.tracks) - 1 if self.tracks else None
        for i, t in enumerate(self.tracks):
            l = self._letter_of(t)
            if l != "#" and l >= letter:
                return i
        return len(self.tracks) - 1 if self.tracks else None

    def jump_to_y(self, y):
        frac = (y - self.rail.y) / max(1, self.rail.h)
        i = min(len(RAIL_LETTERS) - 1, max(0, int(frac * len(RAIL_LETTERS))))
        idx = self.index_for_letter(RAIL_LETTERS[i])
        if idx is not None:
            self.list.scroll_to_index(idx)
            self.dirty = True

    def handle_touch(self, pos, kind):
        if self.tracks:
            if kind == "down" and self.rail.collidepoint(pos):
                self._rail_active = True
            if getattr(self, "_rail_active", False):
                if kind in ("down", "move"):
                    self.jump_to_y(pos[1])
                if kind in ("up", "cancel"):
                    self._rail_active = False
                self.dirty = True
                return True
        return super().handle_touch(pos, kind)

    def draw(self, surface):
        self.draw_header(surface)
        if not self.tracks:
            self.empty.draw(surface)
            return
        self.list.draw(surface)
        n = len(RAIL_LETTERS)
        step = self.rail.h / n
        for i, ch in enumerate(RAIL_LETTERS):
            s = text_cache.render(ch, 10, theme.TEXT_DIM)
            surface.blit(s, s.get_rect(center=(self.rail.centerx, int(self.rail.y + step * (i + 0.5)))))

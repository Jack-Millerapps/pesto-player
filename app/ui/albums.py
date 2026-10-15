"""Albums (2-column grid) and album detail."""
import pygame

from ui import theme
from ui import text_cache
from ui.widgets import ScrollList
from ui.songs import BrowseScreen, EmptyState, LIST_TOP, LIST_BOTTOM
from ui.artists import TrackDetailScreen

CELL_W = theme.SCREEN_W // 2
ART = 136
CELL_H = 188


class AlbumsScreen(BrowseScreen):
    title = "Albums"

    def __init__(self, screen_manager, audio_player, music_library, playlist_store=None):
        super().__init__(screen_manager, audio_player, music_library, playlist_store)
        self.albums = []
        self._art = {}
        self._last_x = 0
        self.list = ScrollList((0, LIST_TOP, theme.SCREEN_W, LIST_BOTTOM - LIST_TOP),
                               CELL_H, self._draw_row, self._on_tap)
        self.lists.append(self.list)
        self.empty = EmptyState((0, LIST_TOP, theme.SCREEN_W, LIST_BOTTOM - LIST_TOP),
                                "No albums yet", self._go_add_music)
        self.reload()

    def reload(self):
        self.albums = list(self.music_library.get_albums())
        rows = [self.albums[i:i + 2] for i in range(0, len(self.albums), 2)]
        self.list.set_items(rows)
        self.widgets = [self.list] if self.albums else [self.empty]
        self._art.clear()
        self.dirty = True

    def on_enter(self, **kw):
        self.reload()
        super().on_enter(**kw)

    def _art_for(self, album):
        key = (album.get("title"), album.get("artist"))
        if key not in self._art:
            surf = None
            try:
                tracks = self.music_library.tracks_for_album(*key)
                if tracks:
                    surf = self.music_library.get_art(tracks[0], ART)
            except Exception:
                surf = None
            if len(self._art) > 24:
                self._art.pop(next(iter(self._art)))
            self._art[key] = surf
        return self._art[key]

    def _draw_row(self, surface, rect, item, index, state):
        for c, album in enumerate(item):
            cell = pygame.Rect(rect.x + c * CELL_W, rect.y, CELL_W, rect.h)
            art = pygame.Rect(0, 0, ART, ART)
            art.midtop = (cell.centerx, cell.y + 6)
            img = self._art_for(album)
            if img is not None:
                surface.blit(img, img.get_rect(center=art.center))
            else:
                pygame.draw.rect(surface, theme.BG_PRESSED, art, border_radius=6)
                ch = (album.get("title") or "?")[:1].upper()
                s = text_cache.render(ch, theme.FS_BIG, theme.TEXT_DIM)
                surface.blit(s, s.get_rect(center=art.center))
            w = CELL_W - 16
            t = text_cache.ellipsize(album.get("title") or "Unknown", theme.FS_SMALL + 1, w)
            a = text_cache.ellipsize(album.get("artist") or "", theme.FS_SMALL, w)
            surface.blit(text_cache.render(t, theme.FS_SMALL + 1, theme.TEXT), (cell.x + 8, art.bottom + 4))
            surface.blit(text_cache.render(a, theme.FS_SMALL, theme.TEXT_DIM), (cell.x + 8, art.bottom + 20))

    def handle_touch(self, pos, kind):
        if kind == "down" or kind == "up":
            self._last_x = pos[0]
        return super().handle_touch(pos, kind)

    def _on_tap(self, row, index):
        col = 0 if self._last_x < CELL_W else 1
        if col >= len(row):
            return
        a = row[col]
        self.screen_manager.push("album_detail", title=a.get("title"), artist=a.get("artist"))

    def draw(self, surface):
        self.draw_header(surface)
        (self.list if self.albums else self.empty).draw(surface)


class AlbumDetailScreen(TrackDetailScreen):
    def on_enter(self, title=None, artist=None, **kw):
        if title is not None:
            self.heading = title or "Unknown"
            self.set_tracks(self.music_library.tracks_for_album(title, artist))
        super().on_enter(**kw)

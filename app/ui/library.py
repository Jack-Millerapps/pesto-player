"""Library hub: Songs, Artists, Albums, Playlists, Search, Add music.

Pushes the detail screens by registered name, so main.py (or
register_library_screens below) must register them.
"""
import pygame

from ui import theme
from ui import text_cache
from ui.widgets import ScrollList
from ui.songs import BrowseScreen, LIST_TOP, LIST_BOTTOM, SongsScreen
from ui.artists import ArtistsScreen, ArtistDetailScreen, plural
from ui.albums import AlbumsScreen, AlbumDetailScreen
from ui.playlists import PlaylistsScreen, PlaylistDetailScreen
from ui.search import SearchScreen

HUB_ROW_H = 48
ROWS = [("songs", "Songs"), ("artists", "Artists"), ("albums", "Albums"),
        ("playlists", "Playlists"), ("search", "Search"), ("add_music", "Add music")]


class LibraryScreen(BrowseScreen):
    title = "Library"
    has_back = False

    def __init__(self, screen_manager, audio_player, music_library, playlist_store=None):
        super().__init__(screen_manager, audio_player, music_library, playlist_store)
        self.list = ScrollList((0, LIST_TOP, theme.SCREEN_W, LIST_BOTTOM - LIST_TOP),
                               HUB_ROW_H, self._draw_row, self._on_tap, items=ROWS)
        self.lists.append(self.list)
        self.widgets = [self.list]

    def _subtitle(self, key):
        try:
            if key == "songs":
                return plural(len(self.music_library.get_tracks()), "song")
            if key == "artists":
                return plural(len(self.music_library.get_artists()), "artist")
            if key == "albums":
                return plural(len(self.music_library.get_albums()), "album")
            if key == "playlists":
                return plural(len(self.store.list_names()), "playlist")
        except Exception:
            pass
        return ""

    def on_enter(self, **kw):
        self._counts = {k: self._subtitle(k) for k, _ in ROWS}
        super().on_enter(**kw)

    _counts = {}

    def _draw_row(self, surface, rect, item, index, state):
        key, label = item
        x = rect.x + theme.PAD
        surface.blit(text_cache.render(label, theme.FS_TITLE, theme.TEXT), (x, rect.centery - 12))
        sub = self._counts.get(key, "")
        if sub:
            s = text_cache.render(sub, theme.FS_SMALL, theme.TEXT_DIM)
            surface.blit(s, (rect.right - theme.PAD - 16 - s.get_width(), rect.centery - s.get_height() // 2))
        cx, cy = rect.right - theme.PAD - 4, rect.centery
        pygame.draw.lines(surface, theme.TEXT_DIM, False, [(cx - 4, cy - 6), (cx, cy), (cx - 4, cy + 6)], 2)
        pygame.draw.line(surface, theme.BORDER, (x, rect.bottom - 1), (rect.right, rect.bottom - 1))

    def _on_tap(self, item, index):
        self.screen_manager.push(item[0])

    def draw(self, surface):
        self.draw_header(surface)
        self.list.draw(surface)


def register_library_screens(sm, audio_player, music_library, playlist_store=None):
    """Register the hub (tab 'library') and all its sub-screens. Returns the hub."""
    args = (sm, audio_player, music_library, playlist_store)
    hub = LibraryScreen(*args)
    sm.register("library", hub, tab="library")
    for name, cls in (("songs", SongsScreen), ("artists", ArtistsScreen),
                      ("albums", AlbumsScreen), ("playlists", PlaylistsScreen),
                      ("search", SearchScreen), ("artist_detail", ArtistDetailScreen),
                      ("album_detail", AlbumDetailScreen),
                      ("playlist_detail", PlaylistDetailScreen)):
        sm.register(name, cls(*args))
    return hub

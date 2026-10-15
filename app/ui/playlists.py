"""Playlists list and playlist detail."""
import pygame

from ui import theme
from ui import text_cache
from ui.widgets import Button, ScrollList
from ui.songs import (BrowseScreen, LIST_TOP, LIST_BOTTOM, HEADER_H, next_playlist_name)
from ui.artists import TrackDetailScreen, plural


class PlaylistsScreen(BrowseScreen):
    title = "Playlists"

    def __init__(self, screen_manager, audio_player, music_library, playlist_store=None):
        super().__init__(screen_manager, audio_player, music_library, playlist_store)
        self.names = []
        self._counts = {}
        self.btn_new = Button((theme.SCREEN_W - 70 - 6, theme.CONTENT_TOP, 70, HEADER_H),
                              "New", self.create_playlist, style="secondary")
        self.header_buttons.append(self.btn_new)
        self.list = ScrollList((0, LIST_TOP, theme.SCREEN_W, LIST_BOTTOM - LIST_TOP),
                               theme.ROW_H, self._draw_row, self._on_tap, self._on_long)
        self.lists.append(self.list)
        self.widgets = [self.list]
        self.reload()

    def reload(self):
        self.names = list(self.store.list_names())
        self._counts = {}
        for n in self.names:
            try:
                self._counts[n] = len(self.store.load(n))
            except Exception:
                self._counts[n] = 0
        self.list.set_items(self.names)
        self.dirty = True

    def on_enter(self, **kw):
        self.reload()
        super().on_enter(**kw)

    def create_playlist(self):
        name = next_playlist_name(self.store)
        self.store.save(name, [])
        self.reload()
        self.screen_manager.toast(f"Created {name}")

    def delete_playlist(self, name):
        self.store.delete(name)
        self.reload()
        self.screen_manager.toast(f"Deleted {name}")

    def _draw_row(self, surface, rect, item, index, state):
        x = rect.x + theme.PAD
        n = text_cache.ellipsize(item, theme.FS_BODY, rect.w - 2 * theme.PAD)
        surface.blit(text_cache.render(n, theme.FS_BODY, theme.TEXT), (x, rect.y + 9))
        count = self._counts.get(item, 0)
        surface.blit(text_cache.render(plural(count, "song"), theme.FS_SMALL, theme.TEXT_DIM),
                     (x, rect.y + 31))
        pygame.draw.line(surface, theme.BORDER, (x, rect.bottom - 1), (rect.right, rect.bottom - 1))

    def _on_tap(self, item, index):
        self.screen_manager.push("playlist_detail", playlist_name=item)

    def _on_long(self, item, index):
        self.screen_manager.show_sheet([("Delete playlist", lambda: self.delete_playlist(item))])

    def draw(self, surface):
        self.draw_header(surface)
        if not self.names:
            s = text_cache.render("No playlists. Tap New.", theme.FS_BODY, theme.TEXT_DIM)
            surface.blit(s, s.get_rect(center=(theme.SCREEN_W // 2, 200)))
            return
        self.list.draw(surface)


class PlaylistDetailScreen(TrackDetailScreen):
    name = None

    def on_enter(self, playlist_name=None, **kw):
        if playlist_name is not None:
            self.name = playlist_name
            self.heading = playlist_name
        if self.name is not None:
            self.set_tracks(self.store.load(self.name))
        super().on_enter(**kw)

    def _on_long(self, item, index):
        from ui.songs import track_actions
        track_actions(self.screen_manager, self.audio_player, self.store, item,
                      extra=[("Remove from playlist", lambda: self.remove(index))])

    def remove(self, index):
        if 0 <= index < len(self.tracks):
            tracks = self.tracks[:index] + self.tracks[index + 1:]
            self.store.save(self.name, tracks)
            self.set_tracks(tracks)

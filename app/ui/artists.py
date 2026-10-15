"""Artists list and artist detail (Play / Shuffle + track list)."""
import pygame

from ui import theme
from ui import text_cache
from ui.widgets import Button, ScrollList
from ui.songs import (BrowseScreen, EmptyState, LIST_TOP, LIST_BOTTOM, HEADER_H,
                      draw_track_row, play_tracks, shuffle_start_index, track_actions)


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


class ArtistsScreen(BrowseScreen):
    title = "Artists"

    def __init__(self, screen_manager, audio_player, music_library, playlist_store=None):
        super().__init__(screen_manager, audio_player, music_library, playlist_store)
        self.artists = []
        self.list = ScrollList((0, LIST_TOP, theme.SCREEN_W, LIST_BOTTOM - LIST_TOP),
                               theme.ROW_H, self._draw_row, self._on_tap)
        self.lists.append(self.list)
        self.empty = EmptyState((0, LIST_TOP, theme.SCREEN_W, LIST_BOTTOM - LIST_TOP),
                                "No artists yet", self._go_add_music)
        self.reload()

    def reload(self):
        self.artists = list(self.music_library.get_artists())
        self.list.set_items(self.artists)
        self.widgets = [self.list] if self.artists else [self.empty]
        self.dirty = True

    def on_enter(self, **kw):
        self.reload()
        super().on_enter(**kw)

    def _draw_row(self, surface, rect, item, index, state):
        x = rect.x + theme.PAD
        max_w = rect.w - 2 * theme.PAD
        name = text_cache.ellipsize(item.get("name") or "Unknown", theme.FS_BODY, max_w)
        surface.blit(text_cache.render(name, theme.FS_BODY, theme.TEXT), (x, rect.y + 9))
        sub = f"{plural(item.get('album_count', 0), 'album')}, {plural(item.get('track_count', 0), 'song')}"
        surface.blit(text_cache.render(sub, theme.FS_SMALL, theme.TEXT_DIM), (x, rect.y + 31))
        pygame.draw.line(surface, theme.BORDER, (x, rect.bottom - 1), (rect.right, rect.bottom - 1))

    def _on_tap(self, item, index):
        self.screen_manager.push("artist_detail", artist_name=item.get("name"))

    def draw(self, surface):
        self.draw_header(surface)
        (self.list if self.artists else self.empty).draw(surface)


class TrackDetailScreen(BrowseScreen):
    """Shared body: Play / Shuffle buttons over a track list."""
    BTN_Y = LIST_TOP + 4

    def __init__(self, screen_manager, audio_player, music_library, playlist_store=None):
        super().__init__(screen_manager, audio_player, music_library, playlist_store)
        self.tracks = []
        self.heading = ""
        w = (theme.SCREEN_W - 3 * theme.PAD) // 2
        self.btn_play = Button((theme.PAD, self.BTN_Y, w, theme.MIN_TOUCH), "Play", self._play)
        self.btn_shuffle = Button((2 * theme.PAD + w, self.BTN_Y, w, theme.MIN_TOUCH),
                                  "Shuffle", self._shuffle, style="secondary")
        top = self.BTN_Y + theme.MIN_TOUCH + 4
        self.list = ScrollList((0, top, theme.SCREEN_W, LIST_BOTTOM - top), theme.ROW_H,
                               self._draw_row, self._on_tap, self._on_long)
        self.lists.append(self.list)
        self.widgets = [self.btn_play, self.btn_shuffle, self.list]

    def set_tracks(self, tracks):
        self.tracks = list(tracks)
        self.list.set_items(self.tracks)
        self.list.scroll_to_index(0) if self.tracks else None
        self.dirty = True

    def _play(self):
        play_tracks(self.audio_player, self.tracks, 0, shuffle=False)

    def _shuffle(self):
        play_tracks(self.audio_player, self.tracks, shuffle_start_index(self.tracks), shuffle=True)

    def _draw_row(self, surface, rect, item, index, state):
        draw_track_row(surface, rect, item, item.get("id") == self.current_id,
                       self.thumbs.get(item))

    def _on_tap(self, item, index):
        play_tracks(self.audio_player, self.tracks, index)

    def _on_long(self, item, index):
        track_actions(self.screen_manager, self.audio_player, self.store, item)

    def draw(self, surface):
        self.draw_header(surface, self.heading)
        if not self.tracks:
            s = text_cache.render("No songs", theme.FS_BODY, theme.TEXT_DIM)
            surface.blit(s, s.get_rect(center=(theme.SCREEN_W // 2, 200)))
            return
        self.btn_play.draw(surface)
        self.btn_shuffle.draw(surface)
        self.list.draw(surface)


class ArtistDetailScreen(TrackDetailScreen):
    def on_enter(self, artist_name=None, **kw):
        if artist_name is not None:
            self.heading = artist_name or "Unknown"
            self.set_tracks(self.music_library.tracks_for_artist(artist_name))
        super().on_enter(**kw)

"""Mini-player overlay (48 px) drawn by the shell above the tab bar.

draw(surface), handle_touch(pos, kind) -> bool consumed, update(dt) polls the
player at <= 5 Hz. Tapping the play zone toggles; tapping elsewhere opens Now Playing.
"""
import pygame

from ui import theme, text_cache
from ui.now_playing import track_title, track_artist, draw_icon

POLL_S = 0.2


class MiniPlayer:
    def __init__(self, screen_manager, audio_player, music_library=None):
        self.screen_manager = screen_manager
        self.audio = audio_player
        self.library = music_library
        self.rect = pygame.Rect(0, theme.MINI_Y, theme.SCREEN_W, theme.MINI_H)
        self.play_rect = pygame.Rect(theme.SCREEN_W - 52, theme.MINI_Y + 2, 48, theme.MINI_H - 2)
        self.title = "Nothing playing"
        self.artist = ""
        self.playing = False
        self.progress = 0.0
        self.has_track = False
        self.dirty = True
        self._acc = POLL_S
        self._down = None   # "play" | "body" | None

    def update(self, dt):
        self._acc += dt
        if self._acc < POLL_S:
            return
        self._acc = 0.0
        try:
            st = self.audio.get_state() or {}
        except Exception:
            st = {}
        t = st.get("track")
        title = track_title(t) if t else "Nothing playing"
        artist = track_artist(t) if t else ""
        dur = float(st.get("duration") or (t or {}).get("duration") or 0.0)
        prog = min(1.0, max(0.0, float(st.get("position") or 0.0) / dur)) if dur > 0 else 0.0
        new = (title, artist, bool(st.get("playing")), round(prog * self.rect.w), t is not None)
        if new != (self.title, self.artist, self.playing, round(self.progress * self.rect.w), self.has_track):
            self.title, self.artist, self.playing, self.progress, self.has_track = title, artist, new[2], prog, new[4]
            self.dirty = True

    def handle_touch(self, pos, kind):
        if kind == "down":
            if not self.rect.collidepoint(pos):
                return False
            self._down = "play" if self.play_rect.collidepoint(pos) else "body"
            self.dirty = True
            return True
        if kind == "move":
            return self._down is not None
        if kind == "cancel":
            self._down = None
            self.dirty = True
            return False
        if kind == "up" and self._down:
            what, self._down = self._down, None
            self.dirty = True
            if what == "play" and self.play_rect.collidepoint(pos):
                if self.has_track:
                    self.audio.toggle()
            elif what == "body" and self.rect.collidepoint(pos) and not self.play_rect.collidepoint(pos):
                self.screen_manager.show("now_playing")
            return True
        return False

    def draw(self, surface):
        r = self.rect
        pygame.draw.rect(surface, theme.BG_LIGHT if self._down != "body" else theme.BG_PRESSED, r)
        pygame.draw.line(surface, theme.BORDER, r.topleft, (r.right, r.top))
        if self.progress > 0:
            pygame.draw.rect(surface, theme.PRIMARY, (r.left, r.top, int(r.w * self.progress), 2))
        tw = self.play_rect.left - r.left - 2 * theme.PAD
        t = text_cache.render(text_cache.ellipsize(self.title, theme.FS_BODY, tw), theme.FS_BODY, theme.TEXT, True)
        surface.blit(t, (theme.PAD, r.top + 8))
        if self.artist:
            a = text_cache.render(text_cache.ellipsize(self.artist, theme.FS_SMALL, tw), theme.FS_SMALL, theme.TEXT_DIM)
            surface.blit(a, (theme.PAD, r.top + 28))
        if self._down == "play":
            pygame.draw.circle(surface, theme.BG_PRESSED, self.play_rect.center, 22)
        draw_icon(surface, "pause" if self.playing else "play", self.play_rect,
                  theme.TEXT if self.has_track else theme.TEXT_DISABLED)
        self.dirty = False

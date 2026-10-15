"""Transient volume HUD for hardware volume buttons (visible 1.2 s)."""
import pygame

from ui import theme, text_cache

SHOW_S = 1.2


class VolumeHUD:
    def __init__(self):
        self.volume = 0
        self.remaining = 0.0
        self.dirty = False
        self.rect = pygame.Rect(40, theme.STATUS_H + 6 + 36 + 6, theme.SCREEN_W - 80, 44)

    @property
    def visible(self):
        return self.remaining > 0

    @property
    def active(self):
        return self.remaining > 0

    def show(self, volume):
        self.volume = max(0, min(100, int(volume)))
        self.remaining = SHOW_S
        self.dirty = True

    def update(self, dt):
        if self.remaining > 0:
            self.remaining -= dt
            if self.remaining <= 0:
                self.remaining = 0.0
                # The shell repaints once on active -> inactive; leaving dirty=True here
                # would force a full redraw every frame forever.
                self.dirty = False

    def draw(self, surface):
        if not self.visible:
            return
        r = self.rect
        pygame.draw.rect(surface, theme.TOAST_BG, r, border_radius=10)
        pygame.draw.rect(surface, theme.BORDER, r, 1, border_radius=10)
        label = text_cache.render("Vol", theme.FS_SMALL, theme.TEXT_DIM)
        surface.blit(label, label.get_rect(midleft=(r.left + 10, r.centery)))
        bar = pygame.Rect(r.left + 44, r.centery - 3, r.w - 44 - 52, 6)
        pygame.draw.rect(surface, theme.BG_PRESSED, bar, border_radius=3)
        pygame.draw.rect(surface, theme.PRIMARY, (bar.left, bar.top, int(bar.w * self.volume / 100), bar.h), border_radius=3)
        pct = text_cache.render("%d%%" % self.volume, theme.FS_BODY, theme.TEXT)
        surface.blit(pct, pct.get_rect(midright=(r.right - 10, r.centery)))
        self.dirty = False

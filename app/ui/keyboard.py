"""On-screen keyboard (STUB: signature only; implementation in progress)."""
import pygame


class Keyboard:
    def __init__(self, rect, on_key=None, on_enter=None, on_close=None):
        self.rect = pygame.Rect(rect); self.on_key = on_key
        self.on_enter = on_enter; self.on_close = on_close; self.dirty = True
    def handle_touch(self, pos, kind): return False
    def draw(self, surface): pass

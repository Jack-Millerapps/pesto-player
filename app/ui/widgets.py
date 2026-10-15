"""Reusable widgets (STUB: signatures only; implementation in progress)."""
import pygame


class Button:
    def __init__(self, rect, text="", on_click=None, icon=None, style="primary", enabled=True):
        self.rect = pygame.Rect(rect); self.text = text; self.on_click = on_click
        self.icon = icon; self.style = style; self.enabled = enabled
        self.pressed = False; self.dirty = True
    def handle_touch(self, pos, kind): return False
    def draw(self, surface): pass


class ScrollList:
    def __init__(self, rect, row_h, draw_row, on_tap=None, on_long_press=None, items=None):
        self.rect = pygame.Rect(rect); self.row_h = row_h; self.draw_row = draw_row
        self.on_tap = on_tap; self.on_long_press = on_long_press
        self.items = list(items or []); self.scroll = 0.0; self.dirty = True
    def set_items(self, items): self.items = list(items)
    def scroll_to_index(self, index): pass
    def handle_touch(self, pos, kind): return False
    def update(self, dt): pass
    def draw(self, surface): pass


class Slider:
    def __init__(self, rect, value=0.0, on_change=None, on_commit=None):
        self.rect = pygame.Rect(rect); self.value = value
        self.on_change = on_change; self.on_commit = on_commit; self.dragging = False
        self.dirty = True
    def set_value(self, v): self.value = v
    def handle_touch(self, pos, kind): return False
    def draw(self, surface): pass


class TabBar:
    def __init__(self, rect, tabs, on_select=None):
        self.rect = pygame.Rect(rect); self.tabs = list(tabs)  # [(name, label)]
        self.on_select = on_select; self.active = self.tabs[0][0] if self.tabs else None
        self.dirty = True
    def set_active(self, name): self.active = name
    def handle_touch(self, pos, kind): return False
    def draw(self, surface): pass


class Marquee:
    def __init__(self, rect, text="", size=18, color=(255, 255, 255), bold=False):
        self.rect = pygame.Rect(rect); self.text = text; self.size = size
        self.color = color; self.bold = bold; self.dirty = True
    def set_text(self, text): self.text = text
    def update(self, dt): pass
    def draw(self, surface): pass

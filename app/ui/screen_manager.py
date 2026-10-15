"""Screen manager (STUB: signatures only; implementation in progress)."""
import pygame


class Screen:
    has_mini_player = True   # False on Now Playing
    def __init__(self, screen_manager=None):
        self.screen_manager = screen_manager
        self.dirty = True
    def on_enter(self, **kw): pass
    def on_leave(self): pass
    def handle_touch(self, pos, kind): return False   # kind: down|move|up|cancel
    def update(self, dt): pass
    def draw(self, surface): pass


class StatusBar:
    def __init__(self):
        self.battery_level = 100; self.bluetooth_connected = False; self.dirty = True
    def set_battery_level(self, level): self.battery_level = level
    def set_bluetooth_connected(self, connected): self.bluetooth_connected = connected
    def draw(self, surface): pass


class ScreenManager:
    def __init__(self, display_surface):
        self.display_surface = display_surface
        self.status_bar = StatusBar()
        self.mini_player = None   # set to a Screen-like object with draw/handle_touch
    def register(self, name, screen, tab=None): pass
    def show(self, name, **kw): pass
    def push(self, name, **kw): pass
    def pop(self): return False
    def toast(self, msg, kind="info"): pass
    def show_sheet(self, actions): pass       # actions: [(label, callable)]
    def current_name(self): return None
    def update(self, dt): pass
    def draw(self): return []                 # returns list of dirty pygame.Rect
    def handle_touch(self, pos, kind): return False
    def target_fps(self): return 30

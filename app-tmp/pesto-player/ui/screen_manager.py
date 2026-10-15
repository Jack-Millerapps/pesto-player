"""
Screen Manager for Pesto Player
Handles navigation between different screens (Now Playing, Library, Settings)

Design:
- Maintains a stack of screens for navigation history
- Handles screen transitions
- Routes touch events to the current screen
- Each screen implements: draw(), handle_touch(), update()
"""

import pygame
import config


# ============================================================================
# BASE SCREEN CLASS
# ============================================================================
class Screen:
    """
    Base class for all screens

    Each screen must implement:
    - draw(surface): Draw the screen
    - handle_touch(pos, event_type): Handle touch events
    - update(dt): Update screen state (called every frame)
    """
    def __init__(self, screen_manager):
        self.screen_manager = screen_manager
        self.surface = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))

    def draw(self, surface):
        """Draw the screen - must be overridden"""
        pass

    def handle_touch(self, pos, event_type='down'):
        """Handle touch events - must be overridden"""
        pass

    def update(self, dt):
        """Update screen state - can be overridden"""
        pass

    def on_show(self):
        """Called when screen becomes visible - can be overridden"""
        pass

    def on_hide(self):
        """Called when screen is hidden - can be overridden"""
        pass


# ============================================================================
# SCREEN MANAGER CLASS
# ============================================================================
class ScreenManager:
    """
    Manages screen navigation and rendering

    Features:
    - Screen stack for back navigation
    - Transition effects (future)
    - Event routing to active screen
    """
    def __init__(self, display_surface):
        self.display_surface = display_surface
        self.screens = {}  # Dictionary of screen_name: screen_instance
        self.current_screen = None
        self.screen_stack = []  # Stack for back navigation

    def register_screen(self, name, screen):
        """Register a screen with a name"""
        self.screens[name] = screen

    def show_screen(self, name, add_to_stack=True):
        """
        Switch to a different screen

        Args:
            name: Name of the screen to show
            add_to_stack: If True, add current screen to stack for back navigation
        """
        if name not in self.screens:
            print(f"Warning: Screen '{name}' not found")
            return

        # Hide current screen
        if self.current_screen:
            self.current_screen.on_hide()
            if add_to_stack:
                self.screen_stack.append(self.current_screen)

        # Show new screen
        self.current_screen = self.screens[name]
        self.current_screen.on_show()

    def go_back(self):
        """Go back to the previous screen in the stack"""
        if self.screen_stack:
            if self.current_screen:
                self.current_screen.on_hide()

            self.current_screen = self.screen_stack.pop()
            self.current_screen.on_show()
            return True
        return False

    def update(self, dt):
        """Update the current screen"""
        if self.current_screen:
            self.current_screen.update(dt)

    def draw(self):
        """Draw the current screen"""
        if self.current_screen:
            self.current_screen.draw(self.display_surface)

    def handle_touch(self, pos, event_type='down'):
        """Route touch events to the current screen"""
        if self.current_screen:
            return self.current_screen.handle_touch(pos, event_type)
        return False

    def get_current_screen_name(self):
        """Get the name of the current screen"""
        for name, screen in self.screens.items():
            if screen == self.current_screen:
                return name
        return None


# ============================================================================
# STATUS BAR (shown on all screens)
# ============================================================================
class StatusBar:
    """
    Top status bar showing battery and Bluetooth status
    This is drawn on top of every screen
    """
    def __init__(self):
        self.battery_level = 100
        self.bluetooth_connected = False
        self.font = pygame.font.Font(None, config.FONT_SIZE_SMALL)

    def draw(self, surface):
        """Draw status bar at the top of the screen"""
        # Draw background
        status_rect = pygame.Rect(0, 0, config.SCREEN_WIDTH, config.STATUS_BAR_HEIGHT)
        pygame.draw.rect(surface, config.COLOR_BG_DARKER, status_rect)

        # Draw bottom border
        pygame.draw.line(surface, config.COLOR_BORDER,
                        (0, config.STATUS_BAR_HEIGHT),
                        (config.SCREEN_WIDTH, config.STATUS_BAR_HEIGHT), 1)

        # Battery indicator (left side)
        self._draw_battery(surface)

        # Bluetooth indicator (right side)
        if self.bluetooth_connected:
            self._draw_bluetooth(surface)

    def _draw_battery(self, surface):
        """Draw battery percentage and icon"""
        x = config.STATUS_BAR_PADDING
        y = config.STATUS_BAR_HEIGHT // 2

        # Battery icon (simple rectangle)
        battery_width = 30
        battery_height = 14
        battery_x = x
        battery_y = y - battery_height // 2

        # Battery outline
        pygame.draw.rect(surface, config.COLOR_TEXT_SECONDARY,
                        (battery_x, battery_y, battery_width, battery_height), 1)

        # Battery terminal (small rectangle on right)
        terminal_width = 2
        terminal_height = 8
        pygame.draw.rect(surface, config.COLOR_TEXT_SECONDARY,
                        (battery_x + battery_width, battery_y + 3,
                         terminal_width, terminal_height))

        # Battery fill level
        fill_width = int((battery_width - 4) * (self.battery_level / 100))
        fill_color = config.COLOR_SUCCESS
        if self.battery_level <= config.BATTERY_LOW_WARNING:
            fill_color = config.COLOR_WARNING
        if self.battery_level <= config.BATTERY_CRITICAL:
            fill_color = config.COLOR_ERROR

        if fill_width > 0:
            pygame.draw.rect(surface, fill_color,
                           (battery_x + 2, battery_y + 2,
                            fill_width, battery_height - 4))

        # Battery percentage text
        battery_text = f"{self.battery_level}%"
        text_surface = self.font.render(battery_text, True, config.COLOR_TEXT_SECONDARY)
        surface.blit(text_surface, (battery_x + battery_width + 8, y - text_surface.get_height() // 2))

    def _draw_bluetooth(self, surface):
        """Draw Bluetooth connected indicator"""
        x = config.SCREEN_WIDTH - config.STATUS_BAR_PADDING - 20
        y = config.STATUS_BAR_HEIGHT // 2

        # Simple Bluetooth icon (just text for now, can be improved)
        bt_text = "BT"
        text_surface = self.font.render(bt_text, True, config.COLOR_PRIMARY)
        surface.blit(text_surface, (x, y - text_surface.get_height() // 2))

    def set_battery_level(self, level):
        """Update battery level (0-100)"""
        self.battery_level = max(0, min(100, level))

    def set_bluetooth_connected(self, connected):
        """Update Bluetooth connection status"""
        self.bluetooth_connected = connected

"""
Settings Screen for Pesto Player
Shows app settings and system information

Layout:
- Back button at top
- Settings sections:
  * Audio Output (Speaker/Bluetooth) - future
  * Display settings - future
  * About (version, battery, song count)

Design decisions:
- Simple list-based layout
- Minimal settings for Phase 1
- Focus on displaying system info
"""

import pygame
import config
from ui.screen_manager import Screen
from ui.widgets import Button, Label


# ============================================================================
# SETTINGS SCREEN
# ============================================================================
class SettingsScreen(Screen):
    """
    Settings and about screen

    Features (Phase 1):
    - Display app version
    - Show battery level
    - Show song count
    - Future: Audio output selection, Bluetooth pairing
    """

    def __init__(self, screen_manager, audio_player, music_library):
        super().__init__(screen_manager)
        self.audio_player = audio_player
        self.music_library = music_library

        # Fonts
        self.font_title = pygame.font.Font(None, config.FONT_SIZE_LARGE)
        self.font_section = pygame.font.Font(None, config.FONT_SIZE_MEDIUM)
        self.font_label = pygame.font.Font(None, config.FONT_SIZE_SMALL)

        # Header
        self.header_height = 80

        # Back button
        self.btn_back = Button(
            10,
            35,
            80,
            40,
            "← Back",
            bg_color=config.COLOR_BG_LIGHTER
        )
        self.btn_back.callback = self._on_back

        # Content area
        self.content_y = self.header_height + 20
        self.section_spacing = 40
        self.item_spacing = 25

        # Battery level (will be updated)
        self.battery_level = config.MOCK_BATTERY_LEVEL

        # All buttons
        self.all_buttons = [self.btn_back]

    # ========================================================================
    # DRAWING
    # ========================================================================
    def draw(self, surface):
        """Draw the Settings screen"""
        # Clear background
        surface.fill(config.COLOR_BG_DARK)

        # Draw header background
        pygame.draw.rect(surface, config.COLOR_BG_DARKER,
                        (0, 0, config.SCREEN_WIDTH, self.header_height))

        # Draw title
        title = "Settings"
        title_surface = self.font_title.render(title, True, config.COLOR_TEXT_PRIMARY)
        title_x = (config.SCREEN_WIDTH - title_surface.get_width()) // 2
        surface.blit(title_surface, (title_x, 15))

        # Draw back button
        self.btn_back.draw(surface)

        # Draw separator line
        pygame.draw.line(surface, config.COLOR_BORDER,
                        (0, self.header_height),
                        (config.SCREEN_WIDTH, self.header_height), 1)

        # Draw content
        self._draw_content(surface)

    def _draw_content(self, surface):
        """Draw settings content"""
        y = self.content_y

        # ====================================================================
        # AUDIO OUTPUT SECTION (Placeholder for Phase 2)
        # ====================================================================
        y = self._draw_section_header(surface, "Audio Output", y)

        y = self._draw_setting_item(surface, "Output Mode:", "Internal Speaker", y)

        # Placeholder for Bluetooth button
        y += self.item_spacing

        # ====================================================================
        # SYSTEM INFO SECTION
        # ====================================================================
        y += self.section_spacing
        y = self._draw_section_header(surface, "System", y)

        # Battery level
        battery_text = f"{self.battery_level}%"
        if config.TEST_MODE:
            battery_text += " (mock)"
        y = self._draw_setting_item(surface, "Battery:", battery_text, y)

        # Volume level
        volume = self.audio_player.get_volume()
        y = self._draw_setting_item(surface, "Volume:", f"{volume}%", y)

        # ====================================================================
        # LIBRARY INFO SECTION
        # ====================================================================
        y += self.section_spacing
        y = self._draw_section_header(surface, "Library", y)

        # Song count
        song_count = self.music_library.get_track_count()
        y = self._draw_setting_item(surface, "Songs:", str(song_count), y)

        # Music directory
        y = self._draw_setting_item(surface, "Location:", config.MUSIC_DIRECTORY, y,
                                    value_color=config.COLOR_TEXT_DISABLED)

        # ====================================================================
        # ABOUT SECTION
        # ====================================================================
        y += self.section_spacing
        y = self._draw_section_header(surface, "About", y)

        y = self._draw_setting_item(surface, "App:", "Pesto Player", y)
        y = self._draw_setting_item(surface, "Version:", "1.0.0 - Phase 1", y)

        if config.TEST_MODE:
            y += self.item_spacing
            test_label = "TEST MODE"
            test_surface = self.font_label.render(test_label, True, config.COLOR_WARNING)
            test_x = (config.SCREEN_WIDTH - test_surface.get_width()) // 2
            surface.blit(test_surface, (test_x, y))

    def _draw_section_header(self, surface, title, y):
        """Draw a section header"""
        # Draw section title
        title_surface = self.font_section.render(title, True, config.COLOR_PRIMARY)
        surface.blit(title_surface, (20, y))

        y += 30

        # Draw separator line
        pygame.draw.line(surface, config.COLOR_BORDER,
                        (20, y),
                        (config.SCREEN_WIDTH - 20, y), 1)

        return y + 20

    def _draw_setting_item(self, surface, label, value, y,
                           label_color=None, value_color=None):
        """Draw a setting item with label and value"""
        label_color = label_color or config.COLOR_TEXT_SECONDARY
        value_color = value_color or config.COLOR_TEXT_PRIMARY

        # Draw label (left)
        label_surface = self.font_label.render(label, True, label_color)
        surface.blit(label_surface, (40, y))

        # Draw value (right)
        value_surface = self.font_label.render(value, True, value_color)

        # Truncate value if too long
        max_width = config.SCREEN_WIDTH - 160
        if value_surface.get_width() > max_width:
            while value_surface.get_width() > max_width and len(value) > 3:
                value = value[:-4] + "..."
                value_surface = self.font_label.render(value, True, value_color)

        value_x = config.SCREEN_WIDTH - 40 - value_surface.get_width()
        surface.blit(value_surface, (value_x, y))

        return y + self.item_spacing

    # ========================================================================
    # UPDATE
    # ========================================================================
    def update(self, dt):
        """Update screen state"""
        pass

    # ========================================================================
    # TOUCH HANDLING
    # ========================================================================
    def handle_touch(self, pos, event_type='down'):
        """Handle touch events"""
        if event_type == 'down':
            for button in self.all_buttons:
                if button.handle_touch(pos, 'down'):
                    return True

        elif event_type == 'up':
            for button in self.all_buttons:
                if button.handle_touch(pos, 'up'):
                    return True

        return False

    # ========================================================================
    # CALLBACKS
    # ========================================================================
    def _on_back(self):
        """Go back to Now Playing screen"""
        self.screen_manager.show_screen('now_playing')

    # ========================================================================
    # LIFECYCLE
    # ========================================================================
    def on_show(self):
        """Called when screen becomes visible"""
        pass

    def on_hide(self):
        """Called when screen is hidden"""
        for button in self.all_buttons:
            button.reset_state()

    # ========================================================================
    # PUBLIC METHODS
    # ========================================================================
    def set_battery_level(self, level):
        """Update battery level display"""
        self.battery_level = level

"""
Now Playing Screen for Pesto Player
The main screen showing current song, album art, and playback controls

Layout (320x480):
- Status bar (30px) at top
- Album art (280x280px) centered
- Song info: title, artist, album
- Progress bar with time labels
- Playback controls: Prev, Play/Pause, Next
- Bottom navigation: Library, Settings buttons

Design decisions:
- All touch targets are minimum 60x60px for finger-friendly interface
- Visual feedback on all button presses
- Clean, minimal design focused on album art
- Progress bar is draggable for seeking
"""

import pygame
import config
from ui.screen_manager import Screen
from ui.widgets import IconButton, Button, ProgressBar, Label, format_time


# ============================================================================
# NOW PLAYING SCREEN
# ============================================================================
class NowPlayingScreen(Screen):
    """
    Main screen showing current track and playback controls

    Features:
    - Large album art display
    - Song metadata (title, artist, album)
    - Playback controls (play/pause/skip)
    - Seekable progress bar
    - Navigation to Library and Settings
    """

    def __init__(self, screen_manager, audio_player):
        super().__init__(screen_manager)
        self.audio_player = audio_player

        # Fonts
        self.font_title = pygame.font.Font(None, config.FONT_SIZE_LARGE)
        self.font_artist = pygame.font.Font(None, config.FONT_SIZE_MEDIUM)
        self.font_album = pygame.font.Font(None, config.FONT_SIZE_SMALL)
        self.font_time = pygame.font.Font(None, config.FONT_SIZE_SMALL)

        # Layout constants
        self.album_art_rect = pygame.Rect(
            (config.SCREEN_WIDTH - config.ALBUM_ART_SIZE) // 2,
            config.ALBUM_ART_Y,
            config.ALBUM_ART_SIZE,
            config.ALBUM_ART_SIZE
        )

        # Placeholder album art (dark square)
        self.album_art_surface = pygame.Surface((config.ALBUM_ART_SIZE, config.ALBUM_ART_SIZE))
        self.album_art_surface.fill(config.COLOR_BG_LIGHTER)

        # Track info positions
        self.title_y = self.album_art_rect.bottom + 20
        self.artist_y = self.title_y + 30
        self.album_y = self.artist_y + 25

        # Progress bar
        progress_y = self.album_y + 40
        self.progress_bar = ProgressBar(
            40,  # x
            progress_y,
            config.SCREEN_WIDTH - 80,  # width
            30  # height (includes touch area)
        )
        self.progress_bar.on_seek = self._on_seek

        # Time labels
        self.time_labels_y = progress_y + 35

        # Control buttons
        controls_y = self.time_labels_y + 40

        self.btn_prev = IconButton(
            config.SCREEN_WIDTH // 2 - config.BUTTON_LARGE - 20,
            controls_y,
            config.BUTTON_MEDIUM,
            'prev',
            bg_color=config.COLOR_BG_LIGHTER
        )
        self.btn_prev.callback = self._on_prev

        self.btn_play_pause = IconButton(
            config.SCREEN_WIDTH // 2 - config.BUTTON_LARGE // 2,
            controls_y - 5,  # Slightly higher
            config.BUTTON_LARGE,
            'play',
            bg_color=config.COLOR_PRIMARY
        )
        self.btn_play_pause.callback = self._on_play_pause

        self.btn_next = IconButton(
            config.SCREEN_WIDTH // 2 + 20,
            controls_y,
            config.BUTTON_MEDIUM,
            'next',
            bg_color=config.COLOR_BG_LIGHTER
        )
        self.btn_next.callback = self._on_next

        # Bottom navigation buttons
        nav_y = config.SCREEN_HEIGHT - config.NAV_BAR_HEIGHT - 10

        self.btn_library = Button(
            20,
            nav_y,
            config.NAV_BAR_BUTTON_WIDTH,
            config.BUTTON_SMALL,
            "Library",
            bg_color=config.COLOR_BG_LIGHTER
        )
        self.btn_library.callback = self._on_library

        self.btn_settings = Button(
            config.SCREEN_WIDTH - config.NAV_BAR_BUTTON_WIDTH - 20,
            nav_y,
            config.NAV_BAR_BUTTON_WIDTH,
            config.BUTTON_SMALL,
            "Settings",
            bg_color=config.COLOR_BG_LIGHTER
        )
        self.btn_settings.callback = self._on_settings

        # Current track info (cached for display)
        self.current_track_info = {
            'title': 'No Track Playing',
            'artist': 'Select a song from Library',
            'album': ''
        }

        # Button tracking for touch feedback
        self.all_buttons = [
            self.btn_prev,
            self.btn_play_pause,
            self.btn_next,
            self.btn_library,
            self.btn_settings
        ]

    # ========================================================================
    # DRAWING
    # ========================================================================
    def draw(self, surface):
        """Draw the Now Playing screen"""
        # Clear background
        surface.fill(config.COLOR_BG_DARK)

        # Draw album art
        surface.blit(self.album_art_surface, self.album_art_rect)

        # Draw album art border
        pygame.draw.rect(surface, config.COLOR_BORDER, self.album_art_rect, 2)

        # Draw track info
        self._draw_track_info(surface)

        # Draw progress bar
        self.progress_bar.draw(surface)

        # Draw time labels
        self._draw_time_labels(surface)

        # Draw control buttons
        self.btn_prev.draw(surface)
        self.btn_play_pause.draw(surface)
        self.btn_next.draw(surface)

        # Draw navigation buttons
        self.btn_library.draw(surface)
        self.btn_settings.draw(surface)

    def _draw_track_info(self, surface):
        """Draw song title, artist, and album"""
        # Title (large, centered)
        title = self.current_track_info['title']
        title_surface = self.font_title.render(title, True, config.COLOR_TEXT_PRIMARY)

        # Truncate if too long
        if title_surface.get_width() > config.SCREEN_WIDTH - 40:
            # Simple truncation
            while title_surface.get_width() > config.SCREEN_WIDTH - 40 and len(title) > 3:
                title = title[:-4] + "..."
                title_surface = self.font_title.render(title, True, config.COLOR_TEXT_PRIMARY)

        title_x = (config.SCREEN_WIDTH - title_surface.get_width()) // 2
        surface.blit(title_surface, (title_x, self.title_y))

        # Artist (medium, centered)
        artist = self.current_track_info['artist']
        artist_surface = self.font_artist.render(artist, True, config.COLOR_TEXT_SECONDARY)

        if artist_surface.get_width() > config.SCREEN_WIDTH - 40:
            while artist_surface.get_width() > config.SCREEN_WIDTH - 40 and len(artist) > 3:
                artist = artist[:-4] + "..."
                artist_surface = self.font_artist.render(artist, True, config.COLOR_TEXT_SECONDARY)

        artist_x = (config.SCREEN_WIDTH - artist_surface.get_width()) // 2
        surface.blit(artist_surface, (artist_x, self.artist_y))

        # Album (small, centered)
        album = self.current_track_info['album']
        if album:
            album_surface = self.font_album.render(album, True, config.COLOR_TEXT_DISABLED)

            if album_surface.get_width() > config.SCREEN_WIDTH - 40:
                while album_surface.get_width() > config.SCREEN_WIDTH - 40 and len(album) > 3:
                    album = album[:-4] + "..."
                    album_surface = self.font_album.render(album, True, config.COLOR_TEXT_DISABLED)

            album_x = (config.SCREEN_WIDTH - album_surface.get_width()) // 2
            surface.blit(album_surface, (album_x, self.album_y))

    def _draw_time_labels(self, surface):
        """Draw current position and total duration"""
        position = self.audio_player.get_position()
        duration = self.audio_player.get_duration()

        # Current time (left)
        current_time = format_time(position)
        time_surface = self.font_time.render(current_time, True, config.COLOR_TEXT_SECONDARY)
        surface.blit(time_surface, (45, self.time_labels_y))

        # Total time (right)
        total_time = format_time(duration)
        time_surface = self.font_time.render(total_time, True, config.COLOR_TEXT_SECONDARY)
        time_x = config.SCREEN_WIDTH - 45 - time_surface.get_width()
        surface.blit(time_surface, (time_x, self.time_labels_y))

    # ========================================================================
    # UPDATE
    # ========================================================================
    def update(self, dt):
        """Update screen state"""
        # Update current track info
        current_track = self.audio_player.get_current_track()
        if current_track:
            self.current_track_info = {
                'title': current_track.get('title', 'Unknown Title'),
                'artist': current_track.get('artist', 'Unknown Artist'),
                'album': current_track.get('album', 'Unknown Album')
            }

        # Update progress bar
        if self.audio_player.is_track_playing() and not self.progress_bar.dragging:
            progress = self.audio_player.get_progress()
            self.progress_bar.set_progress(progress)

        # Update play/pause button icon
        if self.audio_player.is_playing:
            self.btn_play_pause.icon_type = 'pause'
        else:
            self.btn_play_pause.icon_type = 'play'

    # ========================================================================
    # TOUCH HANDLING
    # ========================================================================
    def handle_touch(self, pos, event_type='down'):
        """Handle touch events"""
        if event_type == 'down':
            # Check all buttons
            for button in self.all_buttons:
                if button.handle_touch(pos, 'down'):
                    return True

            # Check progress bar
            if self.progress_bar.handle_touch(pos, 'down'):
                return True

        elif event_type == 'up':
            # Handle button releases
            for button in self.all_buttons:
                if button.handle_touch(pos, 'up'):
                    return True

            # Handle progress bar release
            if self.progress_bar.handle_touch(pos, 'up'):
                return True

        elif event_type == 'motion':
            # Handle progress bar dragging
            if self.progress_bar.handle_touch(pos, 'motion'):
                return True

        return False

    # ========================================================================
    # CALLBACKS
    # ========================================================================
    def _on_play_pause(self):
        """Handle play/pause button"""
        self.audio_player.toggle_play_pause()

    def _on_next(self):
        """Handle next button"""
        self.audio_player.next_track()

    def _on_prev(self):
        """Handle previous button"""
        self.audio_player.previous_track()

    def _on_seek(self, position):
        """Handle seeking via progress bar"""
        # position is 0.0 to 1.0
        duration = self.audio_player.get_duration()
        seek_time = position * duration
        self.audio_player.seek(seek_time)

    def _on_library(self):
        """Navigate to Library screen"""
        self.screen_manager.show_screen('library')

    def _on_settings(self):
        """Navigate to Settings screen"""
        self.screen_manager.show_screen('settings')

    # ========================================================================
    # LIFECYCLE
    # ========================================================================
    def on_show(self):
        """Called when screen becomes visible"""
        # Update track info
        self.update(0)

    def on_hide(self):
        """Called when screen is hidden"""
        # Reset button states
        for button in self.all_buttons:
            button.reset_state()

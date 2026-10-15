"""
Library Screen for Pesto Player
Shows list of local music files

Layout:
- Back button at top
- Tab bar: "Local Files" | "Spotify" (Spotify disabled for Phase 1)
- Scrollable list of songs
- Each song shows: Title, Artist

Design decisions:
- Simple scrollable list with touch interaction
- Tapping a song plays it immediately
- Clean, minimal design matching Now Playing screen
"""

import pygame
import config
from ui.screen_manager import Screen
from ui.widgets import Button, ScrollableList


# ============================================================================
# LIBRARY SCREEN
# ============================================================================
class LibraryScreen(Screen):
    """
    Screen showing music library

    Features:
    - Scrollable list of songs
    - Search functionality (future)
    - Tab for Spotify integration (future)
    """

    def __init__(self, screen_manager, audio_player, music_library):
        super().__init__(screen_manager)
        self.audio_player = audio_player
        self.music_library = music_library

        # Fonts
        self.font_title = pygame.font.Font(None, config.FONT_SIZE_LARGE)
        self.font_tab = pygame.font.Font(None, config.FONT_SIZE_MEDIUM)

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

        # Tab bar
        self.tab_y = self.header_height
        self.tab_height = config.TAB_HEIGHT
        self.active_tab = 'local'  # 'local' or 'spotify'

        # Tab buttons
        tab_width = config.SCREEN_WIDTH // 2
        self.btn_tab_local = Button(
            0,
            self.tab_y,
            tab_width,
            self.tab_height,
            "Local Files",
            bg_color=config.COLOR_PRIMARY,
            border_radius=0
        )
        self.btn_tab_local.callback = self._on_tab_local

        self.btn_tab_spotify = Button(
            tab_width,
            self.tab_y,
            tab_width,
            self.tab_height,
            "Spotify",
            bg_color=config.COLOR_BG_LIGHTER,
            border_radius=0
        )
        self.btn_tab_spotify.callback = self._on_tab_spotify
        self.btn_tab_spotify.enabled = False  # Disabled for Phase 1

        # Song list
        list_y = self.tab_y + self.tab_height
        list_height = config.SCREEN_HEIGHT - list_y

        self.song_list = ScrollableList(
            0,
            list_y,
            config.SCREEN_WIDTH,
            list_height
        )

        # Track if library is loaded
        self.library_loaded = False

        # All buttons for touch handling
        self.all_buttons = [
            self.btn_back,
            self.btn_tab_local,
            self.btn_tab_spotify
        ]

    # ========================================================================
    # DRAWING
    # ========================================================================
    def draw(self, surface):
        """Draw the Library screen"""
        # Clear background
        surface.fill(config.COLOR_BG_DARK)

        # Draw header background
        pygame.draw.rect(surface, config.COLOR_BG_DARKER,
                        (0, 0, config.SCREEN_WIDTH, self.header_height))

        # Draw title
        title = "Music Library"
        title_surface = self.font_title.render(title, True, config.COLOR_TEXT_PRIMARY)
        title_x = (config.SCREEN_WIDTH - title_surface.get_width()) // 2
        surface.blit(title_surface, (title_x, 15))

        # Draw back button
        self.btn_back.draw(surface)

        # Draw separator line
        pygame.draw.line(surface, config.COLOR_BORDER,
                        (0, self.header_height),
                        (config.SCREEN_WIDTH, self.header_height), 1)

        # Draw tabs
        self.btn_tab_local.draw(surface)
        self.btn_tab_spotify.draw(surface)

        # Draw tab separator
        tab_width = config.SCREEN_WIDTH // 2
        pygame.draw.line(surface, config.COLOR_BORDER,
                        (tab_width, self.tab_y),
                        (tab_width, self.tab_y + self.tab_height), 1)

        # Draw tab bottom border
        pygame.draw.line(surface, config.COLOR_BORDER,
                        (0, self.tab_y + self.tab_height),
                        (config.SCREEN_WIDTH, self.tab_y + self.tab_height), 1)

        # Draw content based on active tab
        if self.active_tab == 'local':
            self._draw_local_files(surface)
        else:
            self._draw_spotify_tab(surface)

    def _draw_local_files(self, surface):
        """Draw local files list"""
        if not self.library_loaded:
            # Show loading message
            message = "Loading library..."
            message_surface = self.font_tab.render(message, True, config.COLOR_TEXT_SECONDARY)
            message_x = (config.SCREEN_WIDTH - message_surface.get_width()) // 2
            message_y = (config.SCREEN_HEIGHT - message_surface.get_height()) // 2
            surface.blit(message_surface, (message_x, message_y))
        elif self.song_list.items:
            # Draw song list
            self.song_list.draw(surface)
        else:
            # Show "no music" message
            message1 = "No music found"
            message2 = f"Add MP3 files to {config.MUSIC_DIRECTORY}"

            msg1_surface = self.font_tab.render(message1, True, config.COLOR_TEXT_PRIMARY)
            msg2_surface = self.font_tab.render(message2, True, config.COLOR_TEXT_SECONDARY)

            msg1_x = (config.SCREEN_WIDTH - msg1_surface.get_width()) // 2
            msg1_y = (config.SCREEN_HEIGHT - 50) // 2

            msg2_x = (config.SCREEN_WIDTH - msg2_surface.get_width()) // 2
            msg2_y = msg1_y + 30

            surface.blit(msg1_surface, (msg1_x, msg1_y))
            surface.blit(msg2_surface, (msg2_x, msg2_y))

    def _draw_spotify_tab(self, surface):
        """Draw Spotify tab (disabled for Phase 1)"""
        message = "Spotify coming soon..."
        message_surface = self.font_tab.render(message, True, config.COLOR_TEXT_DISABLED)
        message_x = (config.SCREEN_WIDTH - message_surface.get_width()) // 2
        message_y = (config.SCREEN_HEIGHT - message_surface.get_height()) // 2
        surface.blit(message_surface, (message_x, message_y))

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
            # Check buttons
            for button in self.all_buttons:
                if button.handle_touch(pos, 'down'):
                    return True

            # Check song list
            if self.active_tab == 'local':
                if self.song_list.handle_touch(pos, 'down'):
                    return True

        elif event_type == 'up':
            # Handle button releases
            for button in self.all_buttons:
                if button.handle_touch(pos, 'up'):
                    return True

            # Handle song list
            if self.active_tab == 'local':
                if self.song_list.handle_touch(pos, 'up'):
                    return True

        elif event_type == 'motion':
            # Handle list scrolling
            if self.active_tab == 'local':
                if self.song_list.handle_touch(pos, 'motion'):
                    return True

        return False

    # ========================================================================
    # CALLBACKS
    # ========================================================================
    def _on_back(self):
        """Go back to Now Playing screen"""
        self.screen_manager.show_screen('now_playing')

    def _on_tab_local(self):
        """Switch to Local Files tab"""
        self.active_tab = 'local'
        self.btn_tab_local.bg_color = config.COLOR_PRIMARY
        self.btn_tab_spotify.bg_color = config.COLOR_BG_LIGHTER

    def _on_tab_spotify(self):
        """Switch to Spotify tab"""
        if self.btn_tab_spotify.enabled:
            self.active_tab = 'spotify'
            self.btn_tab_local.bg_color = config.COLOR_BG_LIGHTER
            self.btn_tab_spotify.bg_color = config.COLOR_PRIMARY

    def _on_song_click(self, list_item):
        """Handle song click - play the song"""
        track = list_item.data

        if track:
            # Set queue to all songs, starting from clicked song
            all_tracks = self.music_library.get_all_tracks()
            track_index = all_tracks.index(track)

            # Reorder queue to start from clicked track
            reordered_queue = all_tracks[track_index:] + all_tracks[:track_index]

            self.audio_player.set_queue(reordered_queue)
            self.audio_player.play(track)

            # Go back to Now Playing screen
            self.screen_manager.show_screen('now_playing')

    # ========================================================================
    # LIFECYCLE
    # ========================================================================
    def on_show(self):
        """Called when screen becomes visible"""
        # Load library if not already loaded
        if not self.library_loaded:
            self._load_library()

    def on_hide(self):
        """Called when screen is hidden"""
        # Reset button states
        for button in self.all_buttons:
            button.reset_state()

    # ========================================================================
    # LIBRARY LOADING
    # ========================================================================
    def _load_library(self):
        """Load music library and populate list"""
        print("Loading music library...")

        # Clear existing list
        self.song_list.clear_items()

        # Get all tracks
        tracks = self.music_library.get_all_tracks()

        # Add to list
        for track in tracks:
            title = track.get('title', 'Unknown Title')
            artist = track.get('artist', 'Unknown Artist')
            subtitle = f"{artist}"

            item = self.song_list.add_item(title, subtitle, track)
            item.on_click = self._on_song_click

        self.library_loaded = True
        print(f"Loaded {len(tracks)} tracks into library")

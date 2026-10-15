#!/usr/bin/env python3
"""
Pesto Player - Main Entry Point
A touchscreen music player for Raspberry Pi Zero 2 W

Phase 1 Features:
- Touch-based UI (320x480 portrait mode)
- Local MP3/FLAC playback
- Library browsing
- Playback controls
- Volume control
- Settings screen

Testing Mode:
- Mouse = Touch input
- Arrow keys = Volume control
- ESC = Power button

Author: School Project
Version: 1.0.0 - Phase 1
"""

import pygame
import sys
import os
import config

# Import our modules
from ui.screen_manager import ScreenManager, StatusBar
from ui.now_playing import NowPlayingScreen
from ui.library import LibraryScreen
from ui.settings import SettingsScreen

# Import player modules
from player.audio import AudioPlayer, MockAudioPlayer
from player.library import MusicLibrary, MockMusicLibrary

# Import hardware modules
from hardware.battery import BatteryMonitor, MockBatteryMonitor
from hardware.buttons import ButtonHandler, MockButtonHandler


# ============================================================================
# MAIN APPLICATION CLASS
# ============================================================================
class PestoPlayer:
    """
    Main application class for Pesto Player

    Responsibilities:
    - Initialize pygame and all subsystems
    - Create and manage screens
    - Main event loop
    - Coordinate between UI and hardware
    """

    def __init__(self):
        print("=" * 60)
        print("PESTO PLAYER - Phase 1")
        print("=" * 60)

        # Initialize pygame
        pygame.init()
        pygame.display.set_caption("Pesto Player")

        # Create display surface
        if config.TEST_MODE:
            # Windowed mode for testing
            self.screen = pygame.display.set_mode(
                (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
            )
            print(f"Display: {config.SCREEN_WIDTH}x{config.SCREEN_HEIGHT} (windowed)")
        else:
            # Fullscreen for actual hardware
            self.screen = pygame.display.set_mode(
                (config.SCREEN_WIDTH, config.SCREEN_HEIGHT),
                pygame.FULLSCREEN
            )
            print(f"Display: {config.SCREEN_WIDTH}x{config.SCREEN_HEIGHT} (fullscreen)")

            # Hide mouse cursor in production
            pygame.mouse.set_visible(False)

        # Clock for FPS control
        self.clock = pygame.time.Clock()
        self.running = True

        # Initialize subsystems
        self._init_audio()
        self._init_library()
        self._init_hardware()
        self._init_ui()

        print("Initialization complete!")
        print("-" * 60)

        if config.TEST_MODE:
            print("TEST MODE CONTROLS:")
            print("  Mouse = Touch input")
            print("  Arrow Up/Down = Volume control")
            print("  ESC = Power/Exit")
            print("-" * 60)

    def _init_audio(self):
        """Initialize audio player"""
        print("Initializing audio player...")

        # Try to use real VLC player, fall back to mock if not available
        try:
            self.audio_player = AudioPlayer()
            print("✓ VLC audio player initialized")
        except Exception as e:
            print(f"Warning: Could not initialize VLC: {e}")
            print("Using mock audio player")
            self.audio_player = MockAudioPlayer()

        # Set up audio callbacks
        self.audio_player.on_track_change = self._on_track_change
        self.audio_player.on_playback_state_change = self._on_playback_state_change

    def _init_library(self):
        """Initialize music library"""
        print("Initializing music library...")

        # Check if music directory exists
        music_dir = os.path.expanduser(config.MUSIC_DIRECTORY)

        if os.path.exists(music_dir) and not config.TEST_MODE:
            # Use real library
            self.music_library = MusicLibrary(music_dir)
            track_count = self.music_library.scan()

            if track_count > 0:
                print(f"✓ Found {track_count} tracks in {music_dir}")
            else:
                print(f"Warning: No music files found in {music_dir}")
                print("Using mock library for demonstration")
                self.music_library = MockMusicLibrary()
                self.music_library.scan()
        else:
            # Use mock library for testing
            print(f"Using mock music library (TEST_MODE)")
            self.music_library = MockMusicLibrary()
            self.music_library.scan()

    def _init_hardware(self):
        """Initialize hardware interfaces"""
        print("Initializing hardware...")

        # Battery monitor
        if config.TEST_MODE:
            self.battery = MockBatteryMonitor()
            print("✓ Mock battery monitor")
        else:
            self.battery = BatteryMonitor()
            print("✓ Battery monitor initialized")

        # Button handler
        if config.TEST_MODE:
            self.buttons = MockButtonHandler()
            print("✓ Mock button handler (keyboard)")
        else:
            self.buttons = ButtonHandler()
            print("✓ GPIO button handler")

        # Set up button callbacks
        self.buttons.set_callback('volume_up', self._on_volume_up)
        self.buttons.set_callback('volume_down', self._on_volume_down)
        self.buttons.set_callback('power_short', self._on_power_short)
        self.buttons.set_callback('power_long', self._on_power_long)

    def _init_ui(self):
        """Initialize UI and screens"""
        print("Initializing UI...")

        # Status bar (shown on all screens)
        self.status_bar = StatusBar()
        self.status_bar.set_battery_level(self.battery.get_level())

        # Screen manager
        self.screen_manager = ScreenManager(self.screen)

        # Create screens
        self.now_playing_screen = NowPlayingScreen(
            self.screen_manager,
            self.audio_player
        )

        self.library_screen = LibraryScreen(
            self.screen_manager,
            self.audio_player,
            self.music_library
        )

        self.settings_screen = SettingsScreen(
            self.screen_manager,
            self.audio_player,
            self.music_library
        )

        # Register screens
        self.screen_manager.register_screen('now_playing', self.now_playing_screen)
        self.screen_manager.register_screen('library', self.library_screen)
        self.screen_manager.register_screen('settings', self.settings_screen)

        # Show initial screen
        self.screen_manager.show_screen('now_playing')

        print("✓ UI initialized")

    # ========================================================================
    # MAIN LOOP
    # ========================================================================
    def run(self):
        """Main application loop"""
        print("\nStarting main loop...")
        print("Pesto Player is running!\n")

        # Timers for periodic updates
        last_battery_update = 0
        battery_update_interval = 10.0  # Update battery every 10 seconds

        while self.running:
            # Calculate delta time
            dt = self.clock.tick(config.FPS) / 1000.0  # Convert to seconds

            # Handle events
            self._handle_events()

            # Update subsystems
            self.audio_player.update()
            self.buttons.update()

            # Update battery periodically
            current_time = pygame.time.get_ticks() / 1000.0
            if current_time - last_battery_update >= battery_update_interval:
                self.battery.update()
                self.status_bar.set_battery_level(self.battery.get_level())
                last_battery_update = current_time

            # Update current screen
            self.screen_manager.update(dt)

            # Draw everything
            self._draw()

            # Update display
            pygame.display.flip()

        # Cleanup
        self._cleanup()

    def _handle_events(self):
        """Handle pygame events"""
        for event in pygame.event.get():
            # Quit event
            if event.type == pygame.QUIT:
                self.running = False

            # Mouse button down (touch start)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                pos = event.pos
                self.screen_manager.handle_touch(pos, 'down')

            # Mouse button up (touch end)
            elif event.type == pygame.MOUSEBUTTONUP:
                pos = event.pos
                self.screen_manager.handle_touch(pos, 'up')

            # Mouse motion (touch drag)
            elif event.type == pygame.MOUSEMOTION:
                if event.buttons[0]:  # Left button is pressed
                    pos = event.pos
                    self.screen_manager.handle_touch(pos, 'motion')

            # Keyboard events (for testing)
            elif event.type == pygame.KEYDOWN:
                if config.TEST_MODE and isinstance(self.buttons, MockButtonHandler):
                    self.buttons.handle_key(event.key)

                # Also allow Q to quit in test mode
                if config.TEST_MODE and event.key == pygame.K_q:
                    self.running = False

    def _draw(self):
        """Draw all UI elements"""
        # Draw current screen
        self.screen_manager.draw()

        # Draw status bar on top
        self.status_bar.draw(self.screen)

    # ========================================================================
    # CALLBACKS
    # ========================================================================
    def _on_track_change(self, track):
        """Called when track changes"""
        title = track.get('title', 'Unknown')
        artist = track.get('artist', 'Unknown')
        print(f"♪ Now Playing: {title} - {artist}")

    def _on_playback_state_change(self, is_playing):
        """Called when playback state changes"""
        state = "Playing" if is_playing else "Paused"
        print(f"⏯ Playback: {state}")

    def _on_volume_up(self):
        """Handle volume up button"""
        self.audio_player.volume_up()

    def _on_volume_down(self):
        """Handle volume down button"""
        self.audio_player.volume_down()

    def _on_power_short(self):
        """Handle short power button press"""
        print("Power button pressed (short)")
        # In test mode, exit the app
        if config.TEST_MODE:
            print("Exiting...")
            self.running = False
        # In production, would toggle sleep/wake

    def _on_power_long(self):
        """Handle long power button press"""
        print("Power button pressed (long) - Shutting down")
        self.running = False
        # In production, would initiate system shutdown

    # ========================================================================
    # CLEANUP
    # ========================================================================
    def _cleanup(self):
        """Clean up resources"""
        print("\nShutting down...")

        self.audio_player.cleanup()
        self.buttons.cleanup()

        pygame.quit()
        print("Goodbye!")


# ============================================================================
# ENTRY POINT
# ============================================================================
def main():
    """Main entry point"""
    try:
        app = PestoPlayer()
        app.run()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

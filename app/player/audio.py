"""
Audio Player for Pesto Player
Handles MP3/FLAC playback using python-vlc

Features:
- Play/pause/stop controls
- Next/previous track
- Volume control
- Queue management
- Playback position tracking
- Event callbacks for UI updates

Design decisions:
- Using VLC because it's robust and handles many formats
- Separate from Mopidy integration (Mopidy handles streaming)
- Thread-safe for UI integration
"""

import vlc
import time
import os
import config


# ============================================================================
# AUDIO PLAYER CLASS
# ============================================================================
class AudioPlayer:
    """
    Main audio player class using VLC

    Handles:
    - Local file playback (MP3, FLAC, etc.)
    - Playback control (play, pause, stop, seek)
    - Volume management
    - Queue/playlist management
    """

    def __init__(self):
        # Initialize VLC
        self.instance = vlc.Instance('--no-xlib')  # No X11 for headless operation
        self.player = self.instance.media_player_new()

        # Playback state
        self.is_playing = False
        self.current_track = None
        self.current_track_index = -1

        # Queue
        self.queue = []  # List of track dictionaries

        # Volume (0-100)
        self.volume = config.VOLUME_DEFAULT
        self.player.audio_set_volume(self.volume)

        # Callbacks
        self.on_track_change = None  # Called when track changes: on_track_change(track)
        self.on_playback_state_change = None  # Called when play/pause state changes: on_playback_state_change(is_playing)
        self.on_track_end = None  # Called when track ends: on_track_end()

    # ========================================================================
    # PLAYBACK CONTROL
    # ========================================================================
    def play(self, track=None):
        """
        Start playback

        Args:
            track: Track dictionary to play (if None, resume current track)
        """
        if track:
            self._load_track(track)

        if self.player.get_media():
            self.player.play()
            self.is_playing = True

            if self.on_playback_state_change:
                self.on_playback_state_change(True)

            print(f"Playing: {self.current_track.get('title', 'Unknown')}")
            return True

        return False

    def pause(self):
        """Pause playback"""
        self.player.pause()
        self.is_playing = False

        if self.on_playback_state_change:
            self.on_playback_state_change(False)

    def stop(self):
        """Stop playback"""
        self.player.stop()
        self.is_playing = False

        if self.on_playback_state_change:
            self.on_playback_state_change(False)

    def toggle_play_pause(self):
        """Toggle between play and pause"""
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def next_track(self):
        """Skip to next track in queue"""
        if not self.queue:
            return False

        self.current_track_index = (self.current_track_index + 1) % len(self.queue)
        next_track = self.queue[self.current_track_index]
        self.play(next_track)
        return True

    def previous_track(self):
        """Go to previous track in queue"""
        if not self.queue:
            return False

        # If more than 3 seconds into the song, restart it
        if self.get_position() > 3:
            self.seek(0)
        else:
            # Otherwise go to previous track
            self.current_track_index = (self.current_track_index - 1) % len(self.queue)
            prev_track = self.queue[self.current_track_index]
            self.play(prev_track)

        return True

    # ========================================================================
    # VOLUME CONTROL
    # ========================================================================
    def set_volume(self, volume):
        """
        Set volume (0-100)

        Args:
            volume: Volume level 0-100
        """
        self.volume = max(config.VOLUME_MIN, min(config.VOLUME_MAX, volume))
        self.player.audio_set_volume(self.volume)
        print(f"Volume: {self.volume}%")

    def volume_up(self):
        """Increase volume by step"""
        self.set_volume(self.volume + config.VOLUME_STEP)

    def volume_down(self):
        """Decrease volume by step"""
        self.set_volume(self.volume - config.VOLUME_STEP)

    def get_volume(self):
        """Get current volume (0-100)"""
        return self.volume

    # ========================================================================
    # SEEK / POSITION
    # ========================================================================
    def seek(self, position):
        """
        Seek to position in current track

        Args:
            position: Position in seconds (float)
        """
        if not self.current_track:
            return

        duration = self.get_duration()
        if duration > 0:
            # VLC uses position as 0.0 to 1.0
            normalized_position = position / duration
            self.player.set_position(normalized_position)

    def seek_relative(self, delta_seconds):
        """Seek relative to current position"""
        current_pos = self.get_position()
        self.seek(current_pos + delta_seconds)

    def get_position(self):
        """
        Get current playback position in seconds

        Returns:
            Current position in seconds (float)
        """
        if not self.player.get_media():
            return 0.0

        duration = self.get_duration()
        position = self.player.get_position()  # 0.0 to 1.0

        if duration > 0 and position >= 0:
            return position * duration

        return 0.0

    def get_duration(self):
        """
        Get total duration of current track in seconds

        Returns:
            Duration in seconds (float)
        """
        if not self.current_track:
            return 0.0

        # Try to get duration from track metadata first
        if 'duration' in self.current_track:
            return self.current_track['duration']

        # Otherwise get from VLC
        duration_ms = self.player.get_length()
        if duration_ms > 0:
            return duration_ms / 1000.0

        return 0.0

    def get_progress(self):
        """
        Get playback progress (0.0 to 1.0)

        Returns:
            Progress as float 0.0 to 1.0
        """
        duration = self.get_duration()
        if duration > 0:
            return self.get_position() / duration
        return 0.0

    # ========================================================================
    # QUEUE MANAGEMENT
    # ========================================================================
    def set_queue(self, tracks):
        """
        Set the playback queue

        Args:
            tracks: List of track dictionaries
        """
        self.queue = tracks
        self.current_track_index = -1

    def add_to_queue(self, track):
        """Add a track to the queue"""
        self.queue.append(track)

    def clear_queue(self):
        """Clear the queue"""
        self.queue = []
        self.current_track_index = -1

    def get_queue(self):
        """Get the current queue"""
        return self.queue

    # ========================================================================
    # TRACK INFORMATION
    # ========================================================================
    def get_current_track(self):
        """Get current track information"""
        return self.current_track

    def is_track_playing(self):
        """Check if a track is currently playing"""
        return self.is_playing and self.player.get_state() == vlc.State.Playing

    # ========================================================================
    # UPDATE (call this regularly from main loop)
    # ========================================================================
    def update(self):
        """
        Update player state
        Call this regularly (every frame) to handle events
        """
        # Check if track ended
        if self.is_playing and self.player.get_state() == vlc.State.Ended:
            self.is_playing = False

            if self.on_track_end:
                self.on_track_end()

            # Auto-play next track
            if self.queue and self.current_track_index < len(self.queue) - 1:
                self.next_track()
            else:
                # Queue finished
                if self.on_playback_state_change:
                    self.on_playback_state_change(False)

    # ========================================================================
    # PRIVATE METHODS
    # ========================================================================
    def _load_track(self, track):
        """
        Load a track for playback

        Args:
            track: Track dictionary with 'path' key
        """
        if not track or 'path' not in track:
            print("Error: Invalid track or missing path")
            return False

        path = track['path']

        # Expand user path
        path = os.path.expanduser(path)

        if not os.path.exists(path):
            print(f"Error: File not found: {path}")
            return False

        # Create media
        media = self.instance.media_new(path)
        self.player.set_media(media)

        # Update current track
        old_track = self.current_track
        self.current_track = track

        # Find track index in queue
        if track in self.queue:
            self.current_track_index = self.queue.index(track)

        # Notify callback
        if self.on_track_change and old_track != track:
            self.on_track_change(track)

        return True

    # ========================================================================
    # CLEANUP
    # ========================================================================
    def cleanup(self):
        """Clean up resources"""
        self.stop()
        self.player.release()


# ============================================================================
# MOCK AUDIO PLAYER (for testing without VLC)
# ============================================================================
class MockAudioPlayer:
    """
    Mock audio player for testing on systems without VLC
    Simulates playback with timestamps
    """
    def __init__(self):
        self.is_playing = False
        self.current_track = None
        self.current_track_index = -1
        self.queue = []
        self.volume = config.VOLUME_DEFAULT

        # Simulated playback
        self.play_start_time = 0
        self.pause_position = 0

        # Callbacks
        self.on_track_change = None
        self.on_playback_state_change = None
        self.on_track_end = None

    def play(self, track=None):
        if track:
            self.current_track = track
            if track in self.queue:
                self.current_track_index = self.queue.index(track)
            if self.on_track_change:
                self.on_track_change(track)
            self.pause_position = 0

        self.is_playing = True
        self.play_start_time = time.time() - self.pause_position

        if self.on_playback_state_change:
            self.on_playback_state_change(True)

        print(f"[MOCK] Playing: {self.current_track.get('title', 'Unknown') if self.current_track else 'None'}")
        return True

    def pause(self):
        if self.is_playing:
            self.pause_position = self.get_position()
        self.is_playing = False
        if self.on_playback_state_change:
            self.on_playback_state_change(False)

    def stop(self):
        self.is_playing = False
        self.pause_position = 0
        if self.on_playback_state_change:
            self.on_playback_state_change(False)

    def toggle_play_pause(self):
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def next_track(self):
        if not self.queue:
            return False
        self.current_track_index = (self.current_track_index + 1) % len(self.queue)
        self.play(self.queue[self.current_track_index])
        return True

    def previous_track(self):
        if not self.queue:
            return False
        if self.get_position() > 3:
            self.seek(0)
        else:
            self.current_track_index = (self.current_track_index - 1) % len(self.queue)
            self.play(self.queue[self.current_track_index])
        return True

    def set_volume(self, volume):
        self.volume = max(0, min(100, volume))
        print(f"[MOCK] Volume: {self.volume}%")

    def volume_up(self):
        self.set_volume(self.volume + config.VOLUME_STEP)

    def volume_down(self):
        self.set_volume(self.volume - config.VOLUME_STEP)

    def get_volume(self):
        return self.volume

    def seek(self, position):
        self.pause_position = position
        if self.is_playing:
            self.play_start_time = time.time() - position

    def get_position(self):
        if not self.current_track:
            return 0.0
        if self.is_playing:
            return time.time() - self.play_start_time
        return self.pause_position

    def get_duration(self):
        if self.current_track and 'duration' in self.current_track:
            return self.current_track['duration']
        return 180.0  # Default 3 minutes

    def get_progress(self):
        duration = self.get_duration()
        if duration > 0:
            return min(1.0, self.get_position() / duration)
        return 0.0

    def set_queue(self, tracks):
        self.queue = tracks
        self.current_track_index = -1

    def add_to_queue(self, track):
        self.queue.append(track)

    def clear_queue(self):
        self.queue = []
        self.current_track_index = -1

    def get_queue(self):
        return self.queue

    def get_current_track(self):
        return self.current_track

    def is_track_playing(self):
        return self.is_playing

    def update(self):
        # Check if mock track ended
        if self.is_playing and self.get_position() >= self.get_duration():
            self.is_playing = False
            if self.on_track_end:
                self.on_track_end()
            if self.queue and self.current_track_index < len(self.queue) - 1:
                self.next_track()

    def cleanup(self):
        pass

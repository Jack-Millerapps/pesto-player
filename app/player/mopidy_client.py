"""
Mopidy HTTP API Client for Pesto Player
Handles communication with Mopidy server for Spotify streaming

Phase 1: Placeholder - will be implemented in Phase 2
"""

import config


class MopidyClient:
    """
    Mopidy HTTP JSON-RPC client (placeholder for Phase 2)

    Will handle:
    - Search Spotify
    - Get playlists
    - Play tracks
    - Playback control
    """

    def __init__(self):
        self.base_url = config.MOPIDY_BASE_URL
        self.connected = False

    def connect(self):
        """Test connection to Mopidy"""
        # TODO: Implement in Phase 2
        return False

    def search(self, query):
        """Search for tracks"""
        return []

    def get_playlists(self):
        """Get user playlists"""
        return []

    def play_track(self, track_uri):
        """Play a track by URI"""
        pass

    def is_connected(self):
        """Check if connected to Mopidy"""
        return self.connected

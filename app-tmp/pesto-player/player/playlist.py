"""
Playlist Management for Pesto Player

Phase 1: Placeholder - basic queue management handled in audio.py
Phase 2: Will add playlist save/load functionality
"""


class PlaylistManager:
    """Playlist manager (placeholder for Phase 2)"""

    def __init__(self):
        self.playlists = {}

    def create_playlist(self, name):
        """Create a new playlist"""
        self.playlists[name] = []

    def add_to_playlist(self, playlist_name, track):
        """Add track to playlist"""
        if playlist_name in self.playlists:
            self.playlists[playlist_name].append(track)

    def get_playlist(self, name):
        """Get playlist by name"""
        return self.playlists.get(name, [])

    def get_all_playlists(self):
        """Get all playlist names"""
        return list(self.playlists.keys())

    def save_playlists(self):
        """Save playlists to file"""
        # TODO: Implement in Phase 2
        pass

    def load_playlists(self):
        """Load playlists from file"""
        # TODO: Implement in Phase 2
        pass

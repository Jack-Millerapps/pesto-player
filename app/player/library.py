"""
Music Library Management for Pesto Player
Scans local music directory and extracts metadata

Features:
- Scan ~/Music directory for audio files
- Extract metadata (title, artist, album, duration)
- Extract album art from MP3 files
- Cache metadata for performance
- Sort and filter library

Uses mutagen library for metadata extraction
"""

import os
import glob
from pathlib import Path
import config

# Try to import mutagen, but make it optional for testing
try:
    from mutagen import File as MutagenFile
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    from mutagen.id3 import ID3, APIC
    MUTAGEN_AVAILABLE = True
except ImportError:
    print("Warning: mutagen not installed. Metadata extraction will be limited.")
    MUTAGEN_AVAILABLE = False


# ============================================================================
# MUSIC LIBRARY CLASS
# ============================================================================
class MusicLibrary:
    """
    Manages the local music library

    Features:
    - Scan directory for music files
    - Extract metadata using mutagen
    - Provide search/filter functionality
    - Cache results
    """

    def __init__(self, music_dir=None):
        self.music_dir = music_dir or os.path.expanduser(config.MUSIC_DIRECTORY)
        self.tracks = []  # List of track dictionaries
        self.albums = {}  # Dictionary of album -> tracks
        self.artists = {}  # Dictionary of artist -> tracks

    # ========================================================================
    # SCANNING
    # ========================================================================
    def scan(self):
        """
        Scan the music directory for audio files
        Returns number of tracks found
        """
        print(f"Scanning music directory: {self.music_dir}")

        if not os.path.exists(self.music_dir):
            print(f"Music directory not found: {self.music_dir}")
            return 0

        self.tracks = []

        # Find all audio files
        for ext in config.SUPPORTED_FORMATS:
            pattern = os.path.join(self.music_dir, "**", f"*{ext}")
            files = glob.glob(pattern, recursive=True)

            for file_path in files:
                track = self._extract_metadata(file_path)
                if track:
                    self.tracks.append(track)

        # Build artist and album indexes
        self._build_indexes()

        print(f"Found {len(self.tracks)} tracks")
        return len(self.tracks)

    def _extract_metadata(self, file_path):
        """
        Extract metadata from an audio file

        Returns:
            Dictionary with track information or None if failed
        """
        try:
            if MUTAGEN_AVAILABLE:
                return self._extract_metadata_mutagen(file_path)
            else:
                return self._extract_metadata_basic(file_path)
        except Exception as e:
            print(f"Error extracting metadata from {file_path}: {e}")
            return self._extract_metadata_basic(file_path)

    def _extract_metadata_mutagen(self, file_path):
        """Extract metadata using mutagen library"""
        try:
            audio = MutagenFile(file_path, easy=True)

            if audio is None:
                return self._extract_metadata_basic(file_path)

            # Extract basic info
            title = audio.get('title', [None])[0]
            artist = audio.get('artist', [None])[0]
            album = audio.get('album', [None])[0]

            # If no title, use filename
            if not title:
                title = os.path.splitext(os.path.basename(file_path))[0]

            if not artist:
                artist = "Unknown Artist"

            if not album:
                album = "Unknown Album"

            # Get duration
            duration = 0
            if hasattr(audio.info, 'length'):
                duration = int(audio.info.length)

            return {
                'title': title,
                'artist': artist,
                'album': album,
                'duration': duration,
                'path': file_path,
                'filename': os.path.basename(file_path)
            }

        except Exception as e:
            print(f"Mutagen error for {file_path}: {e}")
            return self._extract_metadata_basic(file_path)

    def _extract_metadata_basic(self, file_path):
        """
        Basic metadata extraction without mutagen
        Just uses filename
        """
        filename = os.path.basename(file_path)
        title = os.path.splitext(filename)[0]

        # Try to parse "Artist - Title.mp3" format
        if ' - ' in title:
            parts = title.split(' - ', 1)
            artist = parts[0].strip()
            title = parts[1].strip()
        else:
            artist = "Unknown Artist"

        return {
            'title': title,
            'artist': artist,
            'album': "Unknown Album",
            'duration': 180,  # Default 3 minutes
            'path': file_path,
            'filename': filename
        }

    def _build_indexes(self):
        """Build artist and album indexes for quick lookup"""
        self.albums = {}
        self.artists = {}

        for track in self.tracks:
            # Index by album
            album = track.get('album', 'Unknown Album')
            if album not in self.albums:
                self.albums[album] = []
            self.albums[album].append(track)

            # Index by artist
            artist = track.get('artist', 'Unknown Artist')
            if artist not in self.artists:
                self.artists[artist] = []
            self.artists[artist].append(track)

    # ========================================================================
    # QUERIES
    # ========================================================================
    def get_all_tracks(self):
        """Get all tracks"""
        return self.tracks

    def get_albums(self):
        """Get list of all albums"""
        return list(self.albums.keys())

    def get_artists(self):
        """Get list of all artists"""
        return list(self.artists.keys())

    def get_tracks_by_album(self, album):
        """Get all tracks from a specific album"""
        return self.albums.get(album, [])

    def get_tracks_by_artist(self, artist):
        """Get all tracks by a specific artist"""
        return self.artists.get(artist, [])

    def search(self, query):
        """
        Search for tracks matching query

        Searches in: title, artist, album

        Returns:
            List of matching tracks
        """
        if not query:
            return self.tracks

        query = query.lower()
        results = []

        for track in self.tracks:
            # Search in title, artist, album
            if (query in track.get('title', '').lower() or
                query in track.get('artist', '').lower() or
                query in track.get('album', '').lower()):
                results.append(track)

        return results

    def get_track_count(self):
        """Get total number of tracks"""
        return len(self.tracks)

    # ========================================================================
    # ALBUM ART
    # ========================================================================
    def get_album_art(self, track):
        """
        Extract album art from track

        Returns:
            PIL Image object or None if not found
        """
        if not MUTAGEN_AVAILABLE:
            return None

        try:
            file_path = track.get('path')
            if not file_path or not os.path.exists(file_path):
                return None

            # Try to extract album art
            if file_path.lower().endswith('.mp3'):
                return self._get_mp3_album_art(file_path)
            elif file_path.lower().endswith('.flac'):
                return self._get_flac_album_art(file_path)

        except Exception as e:
            print(f"Error extracting album art: {e}")

        return None

    def _get_mp3_album_art(self, file_path):
        """Extract album art from MP3 file"""
        try:
            audio = MP3(file_path, ID3=ID3)

            # Look for APIC (attached picture) frame
            for tag in audio.tags.values():
                if isinstance(tag, APIC):
                    # Return raw image data
                    return tag.data

        except Exception as e:
            print(f"Error extracting MP3 album art: {e}")

        return None

    def _get_flac_album_art(self, file_path):
        """Extract album art from FLAC file"""
        try:
            audio = FLAC(file_path)

            if audio.pictures:
                # Return the first picture
                return audio.pictures[0].data

        except Exception as e:
            print(f"Error extracting FLAC album art: {e}")

        return None


# ============================================================================
# MOCK LIBRARY (for testing)
# ============================================================================
class MockMusicLibrary:
    """
    Mock music library for testing without actual music files
    Returns fake data
    """
    def __init__(self, music_dir=None):
        self.music_dir = music_dir
        self.tracks = []

    def scan(self):
        """Return mock tracks"""
        self.tracks = [
            {
                'title': 'Bohemian Rhapsody',
                'artist': 'Queen',
                'album': 'A Night at the Opera',
                'duration': 354,
                'path': None,
                'filename': 'bohemian_rhapsody.mp3'
            },
            {
                'title': 'Stairway to Heaven',
                'artist': 'Led Zeppelin',
                'album': 'Led Zeppelin IV',
                'duration': 482,
                'path': None,
                'filename': 'stairway_to_heaven.mp3'
            },
            {
                'title': 'Hotel California',
                'artist': 'Eagles',
                'album': 'Hotel California',
                'duration': 391,
                'path': None,
                'filename': 'hotel_california.mp3'
            },
            {
                'title': 'Imagine',
                'artist': 'John Lennon',
                'album': 'Imagine',
                'duration': 183,
                'path': None,
                'filename': 'imagine.mp3'
            },
            {
                'title': 'Sweet Child O\' Mine',
                'artist': 'Guns N\' Roses',
                'album': 'Appetite for Destruction',
                'duration': 356,
                'path': None,
                'filename': 'sweet_child_o_mine.mp3'
            }
        ]

        print(f"[MOCK] Loaded {len(self.tracks)} tracks")
        return len(self.tracks)

    def get_all_tracks(self):
        return self.tracks

    def get_albums(self):
        return list(set(track['album'] for track in self.tracks))

    def get_artists(self):
        return list(set(track['artist'] for track in self.tracks))

    def get_tracks_by_album(self, album):
        return [t for t in self.tracks if t['album'] == album]

    def get_tracks_by_artist(self, artist):
        return [t for t in self.tracks if t['artist'] == artist]

    def search(self, query):
        if not query:
            return self.tracks
        query = query.lower()
        return [t for t in self.tracks
                if query in t['title'].lower() or
                   query in t['artist'].lower() or
                   query in t['album'].lower()]

    def get_track_count(self):
        return len(self.tracks)

    def get_album_art(self, track):
        return None  # No album art in mock

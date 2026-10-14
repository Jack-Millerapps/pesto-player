/**
 * API Client for Pesto Player Backend
 * Handles all communication with the Python Flask server
 */

import { io, Socket } from 'socket.io-client';

// Types
export interface Track {
  audioUrl?: string;
  creditUrl?: string;
  licenseUrl?: string;
  id: string;
  title: string;
  artist: string;
  album: string;
  duration: number;
  coverUrl: string;
  filepath: string;
}

export interface Album {
  id: string;
  title: string;
  artist: string;
  coverUrl: string;
  trackCount: number;
  tracks?: Track[];
}

export interface Artist {
  id: string;
  name: string;
  albumCount: number;
}

export interface Playlist {
  id: string;
  name: string;
  trackCount: number;
  tracks?: Track[];
}

export interface PlayerStatus {
  isPlaying: boolean;
  volume: number;
  position: number;
  duration: number;
  shuffle: boolean;
  repeat: 'off' | 'all' | 'one';
  currentTrack: Track | null;
  battery: {
    percentage: number;
    status: string;
    color?: string;
  };
}

export interface SearchResults {
  tracks: Track[];
  albums: Album[];
  artists: Artist[];
}

// Configuration
const API_BASE_URL = import.meta.env.VITE_API_URL || window.location.origin;

class PestoAPI {
  private socket: Socket | null = null;
  private statusCallbacks: ((status: PlayerStatus) => void)[] = [];
  private connectionCallbacks: ((connected: boolean) => void)[] = [];
  private _connected = false;

  constructor() {
    this.initializeWebSocket();
  }

  // WebSocket connection
  private initializeWebSocket() {
    this.socket = io(API_BASE_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 10000,
      reconnectionAttempts: Infinity
    });

    this.socket.on('connect', () => {
      console.log('[API] WebSocket connected');
      this.setConnected(true);
    });

    this.socket.on('disconnect', () => {
      console.log('[API] WebSocket disconnected');
      this.setConnected(false);
    });

    this.socket.on('status', (status: PlayerStatus) => {
      this.statusCallbacks.forEach(callback => callback(status));
    });

    this.socket.on('connect_error', () => {
      this.setConnected(false);
    });
  }

  private setConnected(connected: boolean) {
    if (this._connected === connected) return;
    this._connected = connected;
    this.connectionCallbacks.forEach(callback => callback(connected));
  }

  get connected() {
    return this._connected;
  }

  // Subscribe to status updates
  onStatusUpdate(callback: (status: PlayerStatus) => void) {
    this.statusCallbacks.push(callback);
    return () => {
      this.statusCallbacks = this.statusCallbacks.filter(cb => cb !== callback);
    };
  }

  // Subscribe to connect/disconnect events
  onConnectionChange(callback: (connected: boolean) => void) {
    this.connectionCallbacks.push(callback);
    return () => {
      this.connectionCallbacks = this.connectionCallbacks.filter(cb => cb !== callback);
    };
  }

  // Helper for API calls
  private async fetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);

    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.statusText}`);
      }

      const result = await response.json();
      if (result?.success === false) throw new Error(result.error || 'The player could not complete this action');
      return result;
    } finally {
      clearTimeout(timeout);
    }
  }

  // Player Control APIs
  async getPlayerStatus(): Promise<PlayerStatus> {
    return this.fetch<PlayerStatus>('/api/player/status');
  }

  async play(trackId?: string, trackIds?: string[]): Promise<{ success: boolean }> {
    return this.fetch('/api/player/play', {
      method: 'POST',
      body: JSON.stringify({ trackId, trackIds }),
    });
  }

  async pause(): Promise<{ success: boolean }> {
    return this.fetch('/api/player/pause', {
      method: 'POST',
    });
  }

  async togglePlay(): Promise<{ success: boolean; isPlaying: boolean }> {
    return this.fetch('/api/player/toggle', {
      method: 'POST',
    });
  }

  async next(): Promise<{ success: boolean }> {
    return this.fetch('/api/player/next', {
      method: 'POST',
    });
  }

  async previous(): Promise<{ success: boolean }> {
    return this.fetch('/api/player/previous', {
      method: 'POST',
    });
  }

  async seek(position: number): Promise<{ success: boolean }> {
    return this.fetch('/api/player/seek', {
      method: 'POST',
      body: JSON.stringify({ position }),
    });
  }

  async getVolume(): Promise<{ volume: number }> {
    return this.fetch('/api/player/volume');
  }

  async setVolume(volume: number): Promise<{ success: boolean; volume: number }> {
    return this.fetch('/api/player/volume', {
      method: 'POST',
      body: JSON.stringify({ volume }),
    });
  }

  async toggleShuffle(): Promise<{ success: boolean; shuffle: boolean }> {
    return this.fetch('/api/player/shuffle', {
      method: 'POST',
    });
  }

  async toggleRepeat(): Promise<{ success: boolean; repeat: string }> {
    return this.fetch('/api/player/repeat', {
      method: 'POST',
    });
  }

  // Library APIs
  async getTracks(limit?: number, offset?: number): Promise<{ tracks: Track[]; total: number; offset: number }> {
    const params = new URLSearchParams();
    if (limit) params.append('limit', limit.toString());
    if (offset) params.append('offset', offset.toString());

    return this.fetch(`/api/library/tracks?${params}`);
  }

  async getAlbums(): Promise<{ albums: Album[] }> {
    return this.fetch('/api/library/albums');
  }

  async getArtists(): Promise<{ artists: Artist[] }> {
    return this.fetch('/api/library/artists');
  }

  async getAlbum(albumId: string): Promise<{ album: Album }> {
    return this.fetch(`/api/library/album/${albumId}`);
  }

  async search(query: string): Promise<SearchResults> {
    const params = new URLSearchParams({ q: query });
    return this.fetch(`/api/library/search?${params}`);
  }

  // Queue APIs
  async getQueue(): Promise<{ queue: Track[]; currentIndex: number }> {
    return this.fetch('/api/queue');
  }

  async addToQueue(trackId: string): Promise<{ success: boolean }> {
    return this.fetch('/api/queue/add', {
      method: 'POST',
      body: JSON.stringify({ trackId }),
    });
  }

  async clearQueue(): Promise<{ success: boolean }> {
    return this.fetch('/api/queue/clear', {
      method: 'POST',
    });
  }

  // Playlist APIs
  async getPlaylists(): Promise<{ playlists: Playlist[] }> {
    return this.fetch('/api/playlists');
  }

  async getPlaylist(playlistId: string): Promise<Playlist> {
    return this.fetch(`/api/playlists/${playlistId}`);
  }

  // Spotify APIs
  async getSpotifyStatus(): Promise<{ connected: boolean; authenticated: boolean }> {
    return this.fetch('/api/spotify/status');
  }

  async searchSpotify(query: string): Promise<any> {
    const params = new URLSearchParams({ q: query });
    return this.fetch(`/api/spotify/search?${params}`);
  }

  // Cleanup
  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }
}

// Export singleton instance
export const api = new PestoAPI();

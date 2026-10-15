"""
Bluetooth Manager for Pesto Player
Handles Bluetooth pairing and audio output switching

Phase 1: Placeholder - will be implemented in Phase 2
"""

import config


class BluetoothManager:
    """Bluetooth manager (placeholder for Phase 2)"""

    def __init__(self):
        self.connected = False
        self.connected_device = None

    def scan(self):
        """Scan for Bluetooth devices"""
        return []

    def pair(self, device):
        """Pair with a device"""
        pass

    def connect(self, device):
        """Connect to a paired device"""
        pass

    def disconnect(self):
        """Disconnect current device"""
        self.connected = False
        self.connected_device = None

    def is_connected(self):
        """Check if a device is connected"""
        return self.connected

    def get_connected_device(self):
        """Get currently connected device"""
        return self.connected_device

"""
Battery Monitor for Pesto Player
Reads battery level from MAX17048 via I2C

For testing: Returns mock battery level
For production: Reads from actual I2C sensor
"""

import config

# Try to import I2C library, but make it optional for testing
try:
    from board import SCL, SDA
    import busio
    from adafruit_max1704x import MAX17048
    I2C_AVAILABLE = True
except ImportError:
    print("Warning: I2C libraries not available. Using mock battery monitor.")
    I2C_AVAILABLE = False


# ============================================================================
# BATTERY MONITOR CLASS
# ============================================================================
class BatteryMonitor:
    """
    Battery monitor using MAX17048

    Features:
    - Read battery percentage
    - Low battery warnings
    - Update at regular intervals
    """

    def __init__(self):
        self.battery_level = 100
        self.voltage = 4.2

        if not config.TEST_MODE and I2C_AVAILABLE:
            try:
                # Initialize I2C
                i2c = busio.I2C(SCL, SDA)
                self.sensor = MAX17048(i2c)
                print("Battery monitor initialized")
            except Exception as e:
                print(f"Error initializing battery monitor: {e}")
                self.sensor = None
        else:
            self.sensor = None
            print("Using mock battery monitor")

    def update(self):
        """Read current battery level"""
        if self.sensor:
            try:
                self.battery_level = self.sensor.cell_percent
                self.voltage = self.sensor.cell_voltage
            except Exception as e:
                print(f"Error reading battery: {e}")
        else:
            # Mock battery level (slowly decrease for testing)
            # In real testing, this would be constant
            self.battery_level = config.MOCK_BATTERY_LEVEL

    def get_level(self):
        """Get battery level (0-100)"""
        return self.battery_level

    def get_voltage(self):
        """Get battery voltage"""
        return self.voltage

    def is_low(self):
        """Check if battery is low"""
        return self.battery_level <= config.BATTERY_LOW_WARNING

    def is_critical(self):
        """Check if battery is critically low"""
        return self.battery_level <= config.BATTERY_CRITICAL


# ============================================================================
# MOCK BATTERY MONITOR
# ============================================================================
class MockBatteryMonitor:
    """Mock battery monitor for testing"""

    def __init__(self):
        self.battery_level = config.MOCK_BATTERY_LEVEL
        self.voltage = 4.0

    def update(self):
        pass

    def get_level(self):
        return self.battery_level

    def get_voltage(self):
        return self.voltage

    def is_low(self):
        return False

    def is_critical(self):
        return False

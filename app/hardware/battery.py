"""
Battery Monitor for Pesto Player
Reads battery level from MAX17048 via I2C

For testing: Returns mock battery level
For production: Reads from actual I2C sensor
"""

import os

import config

# Try to import I2C library, but make it optional for testing
try:
    from board import SCL, SDA
    import busio
    from adafruit_max1704x import MAX17048
    I2C_AVAILABLE = True
except ImportError:
    print("Warning: I2C libraries not available. Battery will report unknown.")
    I2C_AVAILABLE = False


# ============================================================================
# BATTERY MONITOR CLASS
# ============================================================================
POWER_SUPPLY_DIR = "/sys/class/power_supply"


def _read_sysfs_capacity(base=POWER_SUPPLY_DIR):
    """Percent from the first battery-type supply under /sys, or None."""
    try:
        for name in sorted(os.listdir(base)):
            d = os.path.join(base, name)
            try:
                with open(os.path.join(d, "type")) as f:
                    if f.read().strip() != "Battery":
                        continue
                with open(os.path.join(d, "capacity")) as f:
                    return max(0, min(100, int(f.read().strip())))
            except (OSError, ValueError):
                continue
    except OSError:
        pass
    return None


class BatteryMonitor:
    """
    Real battery level: MAX17048 over I2C, else a /sys/class/power_supply battery.
    get_level() returns an int 0-100, or None when no battery source exists
    (the UI should then hide the percentage instead of showing a fake number).
    """

    def __init__(self):
        self.battery_level = None
        self.voltage = None
        self.sensor = None

        if I2C_AVAILABLE and not config.TEST_MODE:
            try:
                i2c = busio.I2C(SCL, SDA)
                self.sensor = MAX17048(i2c)
                print("Battery monitor initialized (MAX17048)")
            except Exception as e:
                print(f"Battery: MAX17048 unavailable: {e}")
                self.sensor = None
        self.update()

    @property
    def available(self):
        return self.battery_level is not None

    def update(self):
        """Read current battery level (never raises)."""
        level = None
        if self.sensor:
            try:
                level = int(round(self.sensor.cell_percent))
                self.voltage = self.sensor.cell_voltage
            except Exception as e:
                print(f"Battery: read error: {e}")
        if level is None:
            level = _read_sysfs_capacity()
        self.battery_level = None if level is None else max(0, min(100, level))

    def get_level(self):
        return self.battery_level

    def get_voltage(self):
        return self.voltage

    def is_low(self):
        return self.battery_level is not None and self.battery_level <= config.BATTERY_LOW_WARNING

    def is_critical(self):
        return self.battery_level is not None and self.battery_level <= config.BATTERY_CRITICAL


# ============================================================================
# MOCK BATTERY MONITOR
# ============================================================================
class MockBatteryMonitor:
    """Mock battery monitor for testing"""

    def __init__(self):
        self.battery_level = config.MOCK_BATTERY_LEVEL
        self.voltage = 4.0

    available = True

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

"""
Touch Input Handler for Pesto Player
Handles FT6336U touch controller via I2C

For testing: Uses pygame mouse events (handled in main.py)
For production: Will read from I2C touch controller

Phase 1: Touch input is handled directly in main.py via pygame events
Phase 2: Will add direct I2C touch controller support
"""

import config


class TouchController:
    """
    Touch controller interface (placeholder for Phase 2)

    Phase 1: Touch events come from pygame mouse events
    Phase 2: Will read directly from FT6336U via I2C
    """

    def __init__(self):
        self.last_touch = None

    def read(self):
        """
        Read touch input

        Returns:
            Tuple of (x, y) or None if no touch
        """
        # TODO: Implement I2C touch reading in Phase 2
        return None

    def is_touched(self):
        """Check if screen is currently touched"""
        return False

    def calibrate(self):
        """Calibrate touch screen"""
        # TODO: Implement in Phase 2
        pass

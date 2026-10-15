"""
Physical Button Handler for Pesto Player
Handles GPIO buttons: Power, Volume Up, Volume Down

For testing: Uses keyboard input
For production: Uses GPIO pins
"""

import config
import time

# Try to import gpiozero, but make it optional for testing
try:
    from gpiozero import Button as GPIOButton
    GPIO_AVAILABLE = True
except ImportError:
    print("Warning: gpiozero not available. Using keyboard input for buttons.")
    GPIO_AVAILABLE = False


# ============================================================================
# BUTTON HANDLER CLASS
# ============================================================================
class ButtonHandler:
    """
    Physical button handler

    Buttons:
    - Power: Short press = wake/sleep, Long press = shutdown
    - Volume Up: Increase volume
    - Volume Down: Decrease volume

    For testing mode, uses keyboard:
    - ESC = Power
    - Arrow Up = Volume Up
    - Arrow Down = Volume Down
    """

    def __init__(self):
        self.callbacks = {
            'power_short': None,
            'power_long': None,
            'volume_up': None,
            'volume_down': None
        }

        # Track power button press time for long press detection
        self.power_press_start = 0
        self.power_long_press_triggered = False

        if not config.TEST_MODE and GPIO_AVAILABLE:
            self._init_gpio()
        else:
            print("Using keyboard for button input (TEST_MODE)")

    def _init_gpio(self):
        """Initialize GPIO buttons"""
        try:
            self.btn_power = GPIOButton(
                config.GPIO_POWER_BUTTON,
                pull_up=True,
                bounce_time=config.GPIO_BOUNCE_TIME
            )
            self.btn_volume_up = GPIOButton(
                config.GPIO_VOLUME_UP,
                pull_up=True,
                bounce_time=config.GPIO_BOUNCE_TIME
            )
            self.btn_volume_down = GPIOButton(
                config.GPIO_VOLUME_DOWN,
                pull_up=True,
                bounce_time=config.GPIO_BOUNCE_TIME
            )

            # Set up callbacks
            self.btn_power.when_pressed = self._on_power_pressed
            self.btn_power.when_released = self._on_power_released
            self.btn_volume_up.when_pressed = self._on_volume_up
            self.btn_volume_down.when_pressed = self._on_volume_down

            print("GPIO buttons initialized")

        except Exception as e:
            print(f"Error initializing GPIO buttons: {e}")

    def set_callback(self, button_name, callback):
        """
        Set callback for button event

        Args:
            button_name: 'power_short', 'power_long', 'volume_up', 'volume_down'
            callback: Function to call when button is pressed
        """
        if button_name in self.callbacks:
            self.callbacks[button_name] = callback

    def _on_power_pressed(self):
        """Power button pressed"""
        self.power_press_start = time.time()
        self.power_long_press_triggered = False

    def _on_power_released(self):
        """Power button released"""
        if self.power_long_press_triggered:
            return

        press_duration = time.time() - self.power_press_start

        if press_duration >= config.GPIO_LONG_PRESS_TIME:
            # Long press
            if self.callbacks['power_long']:
                self.callbacks['power_long']()
        else:
            # Short press
            if self.callbacks['power_short']:
                self.callbacks['power_short']()

    def _on_volume_up(self):
        """Volume up button pressed"""
        if self.callbacks['volume_up']:
            self.callbacks['volume_up']()

    def _on_volume_down(self):
        """Volume down button pressed"""
        if self.callbacks['volume_down']:
            self.callbacks['volume_down']()

    def update(self):
        """
        Update button state (for long press detection in GPIO mode)
        Call this regularly from main loop
        """
        if not config.TEST_MODE and GPIO_AVAILABLE:
            # Check for long press on power button
            if (self.power_press_start > 0 and
                not self.power_long_press_triggered and
                time.time() - self.power_press_start >= config.GPIO_LONG_PRESS_TIME):

                self.power_long_press_triggered = True
                if self.callbacks['power_long']:
                    self.callbacks['power_long']()

    def cleanup(self):
        """Clean up GPIO resources"""
        if not config.TEST_MODE and GPIO_AVAILABLE:
            try:
                self.btn_power.close()
                self.btn_volume_up.close()
                self.btn_volume_down.close()
            except:
                pass


# ============================================================================
# MOCK BUTTON HANDLER (integrated with pygame keyboard)
# ============================================================================
class MockButtonHandler:
    """
    Mock button handler for testing
    Keyboard events are handled in main loop
    """

    def __init__(self):
        self.callbacks = {
            'power_short': None,
            'power_long': None,
            'volume_up': None,
            'volume_down': None
        }

        print("Mock button handler initialized (use keyboard)")

    def set_callback(self, button_name, callback):
        if button_name in self.callbacks:
            self.callbacks[button_name] = callback

    def handle_key(self, key):
        """
        Handle keyboard input for testing

        Args:
            key: pygame key code
        """
        import pygame

        if key == pygame.K_UP:
            if self.callbacks['volume_up']:
                self.callbacks['volume_up']()
        elif key == pygame.K_DOWN:
            if self.callbacks['volume_down']:
                self.callbacks['volume_down']()
        elif key == pygame.K_ESCAPE:
            if self.callbacks['power_short']:
                self.callbacks['power_short']()

    def update(self):
        pass

    def cleanup(self):
        pass

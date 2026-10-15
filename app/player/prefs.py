"""
User preferences for Settings (screen timeout, brightness), persisted to
config.PREFS_FILE. Volume, shuffle and repeat live in the player's state.json
instead (they persist as the start-up defaults). The sleep timer is runtime-only.
"""

import json
import os
import time

import config

TIMEOUT_CHOICES = [0, 30, 60, 120, 300]        # seconds; 0 = never
BRIGHTNESS_CHOICES = [25, 50, 75, 100]
SLEEP_TIMER_CHOICES = [0, 15, 30, 60]          # minutes; 0 = off


def _next(choices, value):
    try:
        i = choices.index(value)
    except ValueError:
        return choices[0]
    return choices[(i + 1) % len(choices)]


class Prefs:
    def __init__(self, path=None, clock=time.time):
        self.path = path or config.PREFS_FILE
        self._clock = clock
        self.screen_timeout = 60
        self.brightness = 100
        self.sleep_timer_min = 0
        self._sleep_deadline = None
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            t, b = data.get("screen_timeout"), data.get("brightness")
            if t in TIMEOUT_CHOICES:
                self.screen_timeout = t
            if b in BRIGHTNESS_CHOICES:
                self.brightness = b
        except (OSError, ValueError, AttributeError):
            pass

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"screen_timeout": self.screen_timeout,
                           "brightness": self.brightness}, f)
            os.replace(tmp, self.path)
        except OSError as e:
            print(f"Prefs: could not save: {e}")

    def cycle_timeout(self):
        self.screen_timeout = _next(TIMEOUT_CHOICES, self.screen_timeout)
        self.save()

    def cycle_brightness(self):
        self.brightness = _next(BRIGHTNESS_CHOICES, self.brightness)
        self.save()

    def cycle_sleep_timer(self):
        self.sleep_timer_min = _next(SLEEP_TIMER_CHOICES, self.sleep_timer_min)
        self._sleep_deadline = (self._clock() + self.sleep_timer_min * 60
                                if self.sleep_timer_min else None)

    def sleep_timer_remaining(self):
        """Seconds left, or None when off."""
        if self._sleep_deadline is None:
            return None
        return max(0.0, self._sleep_deadline - self._clock())

    def sleep_timer_expired(self):
        """True exactly once when the timer runs out (then it turns itself off)."""
        if self._sleep_deadline is not None and self._clock() >= self._sleep_deadline:
            self._sleep_deadline = None
            self.sleep_timer_min = 0
            return True
        return False

#!/usr/bin/env python3
# Runs the unmodified pygame app on SDL's dummy driver, copies each frame to
# /dev/fb0 (RGB565 on this panel), and turns polled-touch events into pygame
# mouse events. Needed because SDL kmsdrm cannot use the GPU-less SPI panel.
#
# Performance (the SPI panel tops out around 13 fps for full frames):
#  - Partial push: each flip() compares the frame to the previous one row by row
#    and writes only the changed row range to /dev/fb0. An identical frame
#    writes nothing. display.update(rects) pushes just the rows those rects span.
#  - Touch motion is coalesced: at most one MOUSEMOTION per MOTION_MIN_DT seconds,
#    and the final position is always flushed before the button-up event.
#  - Set PESTO_FULL_PUSH=1 to fall back to the old behaviour (push every frame in full).
import os, sys, threading, time, runpy
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

APP_DIR = os.path.expanduser("~/pesto-player/app")
FB = "/dev/fb0"
SYS = "/sys/class/graphics/fb0/"
FULL_PUSH = os.environ.get("PESTO_FULL_PUSH") == "1"
MOTION_MIN_DT = 0.02


def changed_row_range(prev, cur, row_bytes, rows):
    """Return (first, last) inclusive row indices where prev != cur, or None.

    prev/cur are bytes of rows*row_bytes. Fast path: equal buffers -> None."""
    if prev is not None and len(prev) == len(cur):
        if prev == cur:
            return None
        first = 0
        while prev[first * row_bytes:(first + 1) * row_bytes] == cur[first * row_bytes:(first + 1) * row_bytes]:
            first += 1
        last = rows - 1
        while prev[last * row_bytes:(last + 1) * row_bytes] == cur[last * row_bytes:(last + 1) * row_bytes]:
            last -= 1
        return first, last
    return 0, rows - 1


class FbPusher:
    """Writes rows of a pygame surface to the framebuffer fd."""

    def __init__(self, fd, w, h, bpp, stride, pygame, full_push=False):
        self.fd, self.w, self.h, self.bpp, self.stride = fd, w, h, bpp, stride
        self.pg = pygame
        self.full_push = full_push
        self.prev = None
        self.out16 = None
        self.bytes_per_px = bpp // 8
        self.row_bytes = w * self.bytes_per_px
        self.last_rows = 0     # rows written by the most recent push (for tests/diagnostics)

    def _frame_bytes(self, surf):
        if self.bpp == 32:
            return self.pg.image.tostring(surf, "BGRA")
        if self.out16 is None:
            self.out16 = self.pg.Surface((self.w, self.h), 0, 16, (0xF800, 0x07E0, 0x001F, 0))
        self.out16.blit(surf, (0, 0))
        return self.out16.get_buffer().raw

    def _write_rows(self, data, first, last):
        self.last_rows = last - first + 1
        if self.stride == self.row_bytes:
            os.pwrite(self.fd, data[first * self.row_bytes:(last + 1) * self.row_bytes], first * self.stride)
        else:
            for y in range(first, last + 1):
                os.pwrite(self.fd, data[y * self.row_bytes:(y + 1) * self.row_bytes], y * self.stride)

    def push(self, surf, rects=None):
        if surf is None:
            return
        data = self._frame_bytes(surf)
        if self.full_push:
            self._write_rows(data, 0, self.h - 1)
            return
        if rects:
            top = max(0, min(r.top for r in rects))
            bot = min(self.h - 1, max(r.bottom - 1 for r in rects))
            if bot >= top:
                self._write_rows(data, top, bot)
                self.prev = None      # region unknown relative to prev; resync on next flip
            return
        rng = changed_row_range(self.prev, data, self.row_bytes, self.h)
        self.prev = data
        if rng is None:
            self.last_rows = 0
            return
        self._write_rows(data, rng[0], rng[1])


def main():
    bpp = int(open(SYS + "bits_per_pixel").read())
    w, h = map(int, open(SYS + "virtual_size").read().split(","))
    stride = int(open(SYS + "stride").read())
    print(f"fb0: {w}x{h} {bpp}bpp stride={stride} full_push={FULL_PUSH}")
    if bpp not in (16, 32):
        sys.exit("unsupported fb0 depth")

    import pygame
    from evdev import InputDevice, list_devices, ecodes as e

    fb = os.open(FB, os.O_WRONLY)
    pusher = FbPusher(fb, w, h, bpp, stride, pygame, FULL_PUSH)

    def rect_list(a):
        if not a:
            return None
        a = a[0]
        if a is None:
            return None
        if isinstance(a, pygame.Rect):
            return [a]
        try:
            return [pygame.Rect(r) for r in a]
        except TypeError:
            return [pygame.Rect(a)]

    _flip, _update = pygame.display.flip, pygame.display.update
    def flip():
        _flip(); pusher.push(pygame.display.get_surface())
    def update(*a, **k):
        _update(*a, **k); pusher.push(pygame.display.get_surface(), rect_list(a))
    pygame.display.flip, pygame.display.update = flip, update

    def touch_thread():
        dev = None
        for p in list_devices():
            d = InputDevice(p)
            if "FT6336" in d.name:
                dev = d
        if dev is None:
            print("no FT6336 touch device found")
            return
        x = y = 0
        px, py = 0, 0          # last position posted to pygame
        last_motion = 0.0
        down = False
        post = pygame.event.post
        Ev = pygame.event.Event

        def motion(force=False):
            nonlocal px, py, last_motion
            if (x, y) == (px, py):
                return
            now = time.monotonic()
            if force or now - last_motion >= MOTION_MIN_DT:
                post(Ev(pygame.MOUSEMOTION, pos=(x, y), rel=(x - px, y - py), buttons=(1, 0, 0)))
                px, py, last_motion = x, y, now

        for ev in dev.read_loop():
            if ev.type == e.EV_ABS and ev.code == e.ABS_X: x = ev.value
            elif ev.type == e.EV_ABS and ev.code == e.ABS_Y: y = ev.value
            elif ev.type == e.EV_KEY and ev.code == e.BTN_TOUCH:
                if ev.value:
                    down = True
                    px, py = x, y
                    post(Ev(pygame.MOUSEBUTTONDOWN, pos=(x, y), button=1))
                else:
                    if down:
                        motion(force=True)        # flush final position before release
                    down = False
                    post(Ev(pygame.MOUSEBUTTONUP, pos=(x, y), button=1))
            elif ev.type == e.EV_SYN and down:
                motion()

    threading.Thread(target=touch_thread, daemon=True).start()

    os.chdir(APP_DIR)
    sys.path.insert(0, APP_DIR)
    runpy.run_path(os.path.join(APP_DIR, "main.py"), run_name="__main__")


if __name__ == "__main__":
    main()

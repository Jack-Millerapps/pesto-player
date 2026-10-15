#!/usr/bin/env python3
# Runs the unmodified pygame app on SDL's dummy driver, copies each frame to
# /dev/fb0 (RGB565 on this panel), and turns polled-touch events into pygame
# mouse events. Needed because SDL kmsdrm cannot use the GPU-less SPI panel.
import os, sys, threading, runpy
os.environ["SDL_VIDEODRIVER"] = "dummy"

APP_DIR = os.path.expanduser("~/pesto-player/app")
FB = "/dev/fb0"
SYS = "/sys/class/graphics/fb0/"

bpp = int(open(SYS + "bits_per_pixel").read())
w, h = map(int, open(SYS + "virtual_size").read().split(","))
stride = int(open(SYS + "stride").read())
print(f"fb0: {w}x{h} {bpp}bpp stride={stride}")
if bpp not in (16, 32):
    sys.exit("unsupported fb0 depth")

import pygame
from evdev import InputDevice, list_devices, ecodes as e

fb = os.open(FB, os.O_WRONLY)
out16 = None

def push():
    global out16
    surf = pygame.display.get_surface()
    if surf is None:
        return
    if bpp == 32:
        data = pygame.image.tostring(surf, "BGRA")
    else:
        if out16 is None:
            out16 = pygame.Surface((w, h), 0, 16, (0xF800, 0x07E0, 0x001F, 0))
        out16.blit(surf, (0, 0))
        data = out16.get_buffer().raw
    os.pwrite(fb, data, 0)

_flip, _update = pygame.display.flip, pygame.display.update
def flip():
    _flip(); push()
def update(*a, **k):
    _update(*a, **k); push()
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
    down = False
    for ev in dev.read_loop():
        if ev.type == e.EV_ABS and ev.code == e.ABS_X: x = ev.value
        elif ev.type == e.EV_ABS and ev.code == e.ABS_Y: y = ev.value
        elif ev.type == e.EV_KEY and ev.code == e.BTN_TOUCH:
            down = bool(ev.value)
            t = pygame.MOUSEBUTTONDOWN if down else pygame.MOUSEBUTTONUP
            pygame.event.post(pygame.event.Event(t, pos=(x, y), button=1))
        elif ev.type == e.EV_SYN and down:
            pygame.event.post(pygame.event.Event(
                pygame.MOUSEMOTION, pos=(x, y), rel=(0, 0), buttons=(1, 0, 0)))

threading.Thread(target=touch_thread, daemon=True).start()

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)
runpy.run_path(os.path.join(APP_DIR, "main.py"), run_name="__main__")

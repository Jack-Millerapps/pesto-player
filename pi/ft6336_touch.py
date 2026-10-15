#!/usr/bin/env python3
# Polled FT6336 touch -> uinput. Needed because this board's INT line never
# reached GPIO27, so the interrupt-driven kernel driver reported nothing.
# See The-Brain/Jarvis/Resources/Hosyond ST7796 SPI Display and FT6336 Touch on Pi Zero 2 W.md
import time
from smbus2 import SMBus
from evdev import UInput, AbsInfo, ecodes as e

W, H = 320, 480
caps = {
    e.EV_KEY: [e.BTN_TOUCH],
    e.EV_ABS: [
        (e.ABS_X, AbsInfo(0, 0, W - 1, 0, 0, 0)),
        (e.ABS_Y, AbsInfo(0, 0, H - 1, 0, 0, 0)),
    ],
}
try:
    ui = UInput(caps, name="FT6336 poll touch", input_props=[e.INPUT_PROP_DIRECT])
except TypeError:
    ui = UInput(caps, name="FT6336 poll touch")

bus = SMBus(1)
down = False
while True:
    try:
        d = bus.read_i2c_block_data(0x38, 0x02, 5)
    except OSError:
        time.sleep(0.1)
        continue
    if (d[0] & 0x0F) > 0:
        x = ((d[1] & 0x0F) << 8) | d[2]
        y = ((d[3] & 0x0F) << 8) | d[4]
        ui.write(e.EV_ABS, e.ABS_X, min(x, W - 1))
        ui.write(e.EV_ABS, e.ABS_Y, min(y, H - 1))
        if not down:
            ui.write(e.EV_KEY, e.BTN_TOUCH, 1)
            down = True
        ui.syn()
        time.sleep(0.01)
    else:
        if down:
            ui.write(e.EV_KEY, e.BTN_TOUCH, 0)
            ui.syn()
            down = False
        time.sleep(0.02)

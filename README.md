# Pesto Player

Touchscreen music player for a Raspberry Pi Zero 2 W with a Hosyond 4.0" ST7796 SPI display (320x480) and FT6336 capacitive touch.

- `app/` — pygame app (shipped, runs on the Pi). Set `TEST_MODE = False` in `config.py` for hardware.
- `web-ui/` — polished React/Vite web UI (experimental; needs a Flask backend that is not in this repo yet).
- `pi/` — everything that runs on the Pi: polled touch service, framebuffer launcher, systemd units, display init file, config.txt lines.

Hardware setup and why each piece exists: see the Brain note `Hosyond ST7796 SPI Display and FT6336 Touch on Pi Zero 2 W` and `Jarvis/Projects/Pesto Player.md`.

## Pi install (summary)
1. `git clone` this repo to `~/pesto-player`.
2. Build and install the display firmware: `mipi-dbi-cmd st7796.bin pi/st7796.txt && sudo cp st7796.bin /lib/firmware/panel.bin`; append `pi/config.txt.snippet` to `/boot/firmware/config.txt`.
3. `sudo cp pi/ft6336_touch.py /usr/local/bin/` and copy both units from `pi/systemd/` to `/etc/systemd/system/`, then `sudo systemctl enable --now ft6336-touch pesto-player` and `sudo systemctl set-default multi-user.target`.

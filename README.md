# Pesto Player

Touchscreen music player for a Raspberry Pi Zero 2 W with a Hosyond 4.0" ST7796 SPI display (320x480) and FT6336 capacitive touch.

- `app/` — pygame local-music player (runs on the Pi). `TEST_MODE` is auto-detected (framebuffer + GPIO present = hardware); force with `PESTO_TEST=0/1`. No Spotify/Mopidy: local files only.
- `web-ui/` — polished React/Vite web UI (experimental; needs a Flask backend that is not in this repo yet).
- `pi/` — everything that runs on the Pi: polled touch service, framebuffer launcher, Wi-Fi uploader (`pi/uploader/`), systemd units, display init file, config.txt lines.

Hardware setup and why each piece exists: see the Brain note `Hosyond ST7796 SPI Display and FT6336 Touch on Pi Zero 2 W` and `Jarvis/Projects/Pesto Player.md`.

## Pi install (summary)
1. `git clone` this repo to `~/pesto-player`.
2. Build and install the display firmware: `mipi-dbi-cmd st7796.bin pi/st7796.txt && sudo cp st7796.bin /lib/firmware/panel.bin`; append `pi/config.txt.snippet` to `/boot/firmware/config.txt`.
3. `sudo cp pi/ft6336_touch.py /usr/local/bin/` and copy both units from `pi/systemd/` to `/etc/systemd/system/`, then `sudo systemctl enable --now ft6336-touch pesto-uploader pesto-player` and `sudo systemctl set-default multi-user.target`.
4. Dependencies: `sudo apt install python3-pygame python3-vlc vlc-plugin-base python3-mutagen python3-flask python3-qrcode python3-evdev` (see `app/requirements.txt`).

## Adding music
Open Library > Add music on the player, scan the QR code with a phone on the same Wi-Fi, pick songs (mp3 flac m4a ogg wav opus). They land in `~/Music` and the library rescans by itself. The page URL carries a random per-session token, so only someone who can see the player's screen can upload. Delete from the same page.

## Tests
`SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest app/tests pi/uploader` (headless; uses a mock library/player when VLC or a display is missing). Hardware behaviour (touch, audio, uploads from a phone, sleep/shutdown) is verified only by running on the Pi.

## Power button
Short press: screen sleep/wake. Hold 3 s: shutdown (needs polkit or `pi/systemd/pesto-power.sudoers.example`). Settings > Exit and Shut down end the app with status 0 and are not restarted; Restart exits with 3.

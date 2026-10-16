# Bluetooth audio output (Pi -> speaker/headphones)

Pairing is done on the touchscreen (Settings > Bluetooth). No SSH is needed after this one-time setup.

## One-time setup (paste on the Pi)
```
cd ~/pesto-player && git pull
sudo bash pi/bluetooth/setup.sh
sudo reboot
```
Then go to Settings > Bluetooth, tap Scan, put the speaker or headphones in pairing mode, and tap its name. It pairs, trusts and connects, then music switches to it. At boot the app reconnects the last device, and a trusted device that reconnects by itself is picked up within about 8 s.

## What the script does, and why
| Step | Why |
|---|---|
| `bluez pipewire pipewire-pulse pipewire-alsa wireplumber libspa-0.2-bluetooth pulseaudio-utils` | BlueZ handles the radio. PipeWire's Bluetooth plugin (`libspa-0.2-bluetooth`) does the A2DP audio. `pactl` lets the app pick the default output. Pi OS Lite ships without a sound server. |
| `rfkill unblock bluetooth`, enable `bluetooth.service` | The radio is soft-blocked on some images. |
| add `pesto` to `bluetooth`, `audio` | Debian's BlueZ D-Bus policy only lets the `bluetooth` group (or a console session) talk to `org.bluez`. |
| `loginctl enable-linger pesto` | PipeWire is a **user** service. The player is a **system** service with no login session, so without linger no audio server would be running for `pesto`. |
| WirePlumber `with-logind = false` / `seat-monitoring = disabled` | WirePlumber only starts its Bluetooth monitor for a user with an active seat session. A headless player never has one, so connections would fail with `br-connection-profile-unavailable`. |
| drop-in `pesto-player.service.d/bluetooth-audio.conf` | Orders the app after `user@UID.service`, adds the `bluetooth` group, and sets `XDG_RUNTIME_DIR` so VLC (libpulse) and `pactl` find `/run/user/UID/pulse/native`. The app also sets `XDG_RUNTIME_DIR` itself if it is missing (`hardware/bluetooth.ensure_user_audio_env`). The script writes it as a drop-in instead of editing the main unit, so the main unit still starts on an image that has no `bluetooth` group. |

Why linger plus the user's PipeWire, and not a system-wide PipeWire: it is the supported Bookworm layout, `apt upgrade` will not undo it, and the desktop tools (`wpctl`, `pactl`) keep working. The cost is roughly 20-30 MB of RAM for pipewire, pipewire-pulse and wireplumber (estimate, not measured).

## How audio is routed
1. Connect: `bluetoothctl pair/trust/connect`. The app waits up to 8 s for the `bluez_output.<MAC>` sink, makes it the default with `pactl set-default-sink`, and moves VLC's live stream there with `pactl move-sink-input`. If the device came up in a headset profile, it asks for `a2dp-sink`.
2. If routing failed (for example `pactl` is missing), the app restarts the current track at the same position. The new stream opens on whatever the default output now is.
3. Disconnect from the UI: the default sink goes back to the first non-Bluetooth sink and playback continues.
4. Speaker drops mid-song (switched off, out of range): noticed within about 3 s. Playback **pauses**, a toast says so, and the next Play reopens the stream at the same spot on the fallback output. This also works while the screen is asleep (it runs inside `AudioPlayer.update()`).

## Troubleshooting (if you can get a shell)
- `bluetoothctl show`: is there a Controller, and does it say `Powered: yes`?
- `sudo -u pesto XDG_RUNTIME_DIR=/run/user/$(id -u pesto) pactl list short sinks`: a `bluez_output...` line should appear while a device is connected.
- `journalctl -u pesto-player -b | grep -i bluetooth`: the app logs each failure with BlueZ's raw message.
- The "Bluetooth unavailable" card means `bluetoothctl show` found no controller. Check for `dtoverlay=disable-bt` in `/boot/firmware/config.txt` and `systemctl status hciuart bluetooth`.

## Not verified on hardware
None of this has run on a Pi yet. In particular:
- `bluetoothctl --agent NoInputNoOutput pair` as a one-shot command on BlueZ 5.66
- `devices Paired` versus `paired-devices`
- the WirePlumber 0.4 headless override
- sink naming
- VLC's `:start-time` resume
- A2DP quality while Wi-Fi is busy. Wi-Fi and Bluetooth share one radio on the Zero 2 W, so stutter during big uploads is possible.

Speakers that need a PIN or a passkey confirmation are not supported. The agent is "NoInputNoOutput", which works for normal speakers and headphones.

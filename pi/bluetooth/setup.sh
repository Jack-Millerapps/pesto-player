#!/bin/bash
# One-shot Bluetooth audio (A2DP output) setup for Pesto Player on Pi OS Bookworm.
# Run on the Pi:   sudo bash ~/pesto-player/pi/bluetooth/setup.sh        (user: pesto)
#            or:   sudo bash pi/bluetooth/setup.sh someuser
# Safe to re-run. Why each step exists: pi/bluetooth/README.md.
set -euo pipefail

APP_USER="${1:-pesto}"
if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo: sudo bash $0 [$APP_USER]" >&2
    exit 1
fi
id "$APP_USER" >/dev/null 2>&1 || { echo "No such user: $APP_USER" >&2; exit 1; }
APP_UID="$(id -u "$APP_USER")"
APP_HOME="$(getent passwd "$APP_USER" | cut -d: -f6)"
RUNTIME="/run/user/$APP_UID"
as_user() { runuser -u "$APP_USER" -- env XDG_RUNTIME_DIR="$RUNTIME" "$@"; }

echo "== 1/7 packages (BlueZ, PipeWire + its Bluetooth plugin, pactl)"
apt-get update
apt-get install -y bluez pipewire pipewire-pulse pipewire-alsa wireplumber \
    libspa-0.2-bluetooth pulseaudio-utils

echo "== 2/7 unblock and start Bluetooth"
rfkill unblock bluetooth || true
systemctl enable --now bluetooth.service
if grep -qsE '^\s*dtoverlay=disable-bt' /boot/firmware/config.txt; then
    echo "WARNING: /boot/firmware/config.txt has dtoverlay=disable-bt - remove it and reboot." >&2
fi

echo "== 3/7 groups (bluetooth = BlueZ D-Bus access, audio = sound devices)"
usermod -aG bluetooth,audio "$APP_USER"

echo "== 4/7 linger: start $APP_USER's user services (PipeWire) at boot without a login"
loginctl enable-linger "$APP_USER"
for _ in $(seq 1 20); do [ -d "$RUNTIME" ] && break; sleep 0.5; done

echo "== 5/7 WirePlumber: allow Bluetooth without an active seat session (headless)"
WP="$APP_HOME/.config/wireplumber"
install -d -o "$APP_USER" -g "$APP_USER" "$APP_HOME/.config" "$WP" \
    "$WP/bluetooth.lua.d" "$WP/wireplumber.conf.d"
# WirePlumber 0.4.x (Bookworm): Lua config.
cat > "$WP/bluetooth.lua.d/80-pesto-headless.lua" <<'EOF'
-- Pesto Player: no logind seat session on a headless player, so do not wait for one.
bluez_monitor.properties["with-logind"] = false
EOF
# WirePlumber 0.5.x (Trixie and later): SPA-JSON config. Ignored by 0.4.
cat > "$WP/wireplumber.conf.d/80-pesto-headless.conf" <<'EOF'
# Pesto Player: no logind seat session on a headless player, so do not wait for one.
wireplumber.profiles = {
  main = {
    monitor.bluez.seat-monitoring = disabled
  }
}
EOF
chown "$APP_USER:$APP_USER" "$WP/bluetooth.lua.d/80-pesto-headless.lua" \
    "$WP/wireplumber.conf.d/80-pesto-headless.conf"

echo "== 6/7 PipeWire user services for $APP_USER"
as_user systemctl --user daemon-reload || true
as_user systemctl --user enable pipewire.socket pipewire-pulse.socket wireplumber.service || true
as_user systemctl --user start pipewire.socket pipewire-pulse.socket || true
as_user systemctl --user restart pipewire.service pipewire-pulse.service wireplumber.service || true

echo "== 7/7 pesto-player.service drop-in (start after the user session, BlueZ group)"
install -d /etc/systemd/system/pesto-player.service.d
cat > /etc/systemd/system/pesto-player.service.d/bluetooth-audio.conf <<EOF
# Written by pi/bluetooth/setup.sh. The app reaches PipeWire through the pulse
# socket in $RUNTIME, which exists once user@$APP_UID.service (lingering) is up.
[Unit]
Wants=user@$APP_UID.service bluetooth.service
After=user@$APP_UID.service bluetooth.service

[Service]
SupplementaryGroups=bluetooth
Environment=XDG_RUNTIME_DIR=$RUNTIME
EOF
systemctl daemon-reload

echo
echo "== checks"
bluetoothctl show | grep -E 'Controller|Powered' || echo "!! no Bluetooth controller found"
as_user pactl info 2>/dev/null | grep -E 'Server Name|Default Sink' \
    || echo "!! pactl can't reach PipeWire yet (a reboot usually fixes this)"
echo
echo "Done. Reboot now:  sudo reboot"
echo "Then on the player: Settings > Bluetooth > Scan, and tap your speaker or headphones."

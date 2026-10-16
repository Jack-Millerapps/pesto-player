#!/bin/sh
# Installs Tailscale on the Pi and brings it up. Contains no secrets: you approve the login
# in a browser (or export TS_AUTHKEY in your shell for this one command; never commit it).
set -eu
command -v tailscale >/dev/null 2>&1 || curl -fsSL https://tailscale.com/install.sh | sh
sudo systemctl enable --now tailscaled
if [ -n "${TS_AUTHKEY:-}" ]; then
  sudo tailscale up --ssh --hostname=pesto --auth-key="$TS_AUTHKEY"
else
  sudo tailscale up --ssh --hostname=pesto
fi
tailscale ip -4

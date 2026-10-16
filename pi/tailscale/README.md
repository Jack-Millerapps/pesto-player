# Upload music from anywhere (Tailscale)

Tailscale gives the Pi, your Mac and your phone a private encrypted network (a "tailnet").
Nothing is exposed to the public internet and no router ports are opened. Free personal plan is enough.
The uploader already listens on 0.0.0.0:8080, so it is reachable on the Pi's tailnet address with no change.

## One-time, on the Pi (over the keyboard/console or any shell you have)
    curl -fsSL https://tailscale.com/install.sh | sh        # or: sudo ./pi/tailscale/setup.sh
    sudo tailscale up --ssh --hostname=pesto
Open the login URL it prints on any device and approve the Pi. `--ssh` lets Tailscale SSH accept
connections from your tailnet devices (no keys or passwords to manage); omit it if you only want the uploader.
Headless/unattended alternative: create a one-off, expiring auth key in the Tailscale admin console and pass it
on the command line only (`sudo tailscale up --auth-key=...`). Never save it in this repo or a file.
Service starts at boot by itself (`systemctl is-enabled tailscaled`). Check: `tailscale ip -4` and `tailscale status`.
In the admin console you may disable key expiry for the Pi so it stays connected.

## On your Mac and phone
Install the Tailscale app and sign in with the SAME account. The Pi then appears as `pesto`
(MagicDNS name, e.g. `pesto.<tailnet>.ts.net`, or its 100.x.y.z address).

## Uploading
1. Player: Library > Add music > tap "Home Wi-Fi" (top right) so it reads "Anywhere".
   The button only appears when Tailscale is up on the Pi. Scan the QR with a phone running Tailscale,
   or type the URL shown (it contains the session token).
2. Command line from your Mac (needs `--ssh` or normal sshd):
       scp song.mp3 pesto@pesto:Music/
       rsync -avP ~/Music/Album/ pesto@pesto:Music/Album/
   Then on the player tap Rescan library (the web uploader does this automatically; scp does not).

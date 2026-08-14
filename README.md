# device-tracker client (NixOS)

Self-hosted device tracking. This is the **client** side — a small stdlib-only
Python script + a systemd timer that reports a checkin (hostname, IP, OS, CPU,
memory, disk, battery, boot id) to your own server every few minutes.

The server (Flask dashboard + geo-IP map) runs on your homeserver and is
reachable at `https://track.gooseysserver.eu`. The dashboard/GUI is LAN-only;
the checkin endpoint is public so machines report in from anywhere.

## Features

- **Device tracking** — every machine reports hostname, IP, OS, CPU, memory, disk, battery, boot id every ~5 min.
- **Location** — home-pin (Holbæk) when on the LAN, IP-geo when away, and optional GeoClue2 WiFi positioning.
- **Set location from phone** — open `/mobile` on your phone (public, token required), pick a device, share your GPS fix to pin it exactly (far more accurate than the laptop's WiFi/IP positioning).
- **SSID auto-matching** — when you set a location from your phone, optionally enter the WiFi name (SSID) you're on. The laptop then auto-matches its own SSID to that location, so it knows where it is whenever it joins that network — no manual pinning needed each time.
- **Known SSIDs list** — the dashboard's "Known SSIDs" button shows all SSID->location mappings and lets you delete stale ones.
- **PIN gate** — the public mobile endpoints require a PIN (set via `TRACK_PIN` env on the server) in addition to the token, so a leaked token alone isn't enough to move a device.
- **Set home location** — the dashboard's "Set home" button uses your browser's geolocation to set a precise home pin (instead of the default Holbæk coords), so the home-pin is accurate to where you actually live.
- **Auto-cleanup** — devices that haven't checked in for 7 days (configurable via `STALE_DEVICE_SECS`) are removed automatically, so retired machines drop off the dashboard.
- **Frequent-areas report** — the dashboard's "Frequent areas" button clusters location history into the places you spend time (home, work, etc.).

## Endpoints

- `POST /api/checkin` — client reports in (public, token required).
- `GET  /api/devices` — JSON list of devices + last state (LAN-only, token).
- `GET  /api/device-ids` — public list of device IDs (token) — used by the mobile page.
- `POST /api/set-location` — phone GPS sets a device's location + optional SSID mapping (public, token).
- `GET  /api/known-ssids` — list SSID->location mappings (LAN-only, token).
- `DELETE /api/known-ssids/<ssid>` — delete a mapping (LAN-only, token).
- `POST /api/set-home` — set the home location (LAN-only, token).
- `GET  /api/home` — get the current home location (LAN-only, token).
- `GET  /api/frequent-areas` — clustered location history (LAN-only, token).
- `GET  /mobile` — phone GPS page (public, token + PIN).
- `GET  /` — dashboard (LAN-only).
- `GET  /health` — healthcheck (public).

## Install on a NixOS machine (Framework 12, P14s, etc.)

This is a **classic `configuration.nix`** setup — no flakes required.

### 1. Get the module onto the machine

Clone this repo somewhere, e.g. into your home dir:

```bash
cd ~
git clone https://github.com/itsGoomse/device-tracker.git
```

(Or just copy the `nix/` folder — it's self-contained.)

### 2. Import the module in `configuration.nix`

Open `/etc/nixos/configuration.nix` and add:

```nix
{ config, pkgs, lib, ... }:
{
  imports = [
    ./hardware-configuration.nix
    /home/inuk/device-tracker/nix/module.nix   # <-- adjust path to where you cloned
  ];

  # Enable the tracker client with THIS DEVICE's token:
  services.device-tracker = {
    enable = true;
    token = "PASTE-THIS-DEVICES-TOKEN-HERE";   # one token per device
    # server defaults to https://track.gooseysserver.eu
    # intervalSec defaults to 300 (5 min)
  };
}
```

Each device has its **own** token (per-device tokens, one per machine).
Ask your server admin for the token assigned to this device, or generate one
and add it to the server's `TRACK_TOKENS` list.

> `lib` is only needed if your existing config already references it — the
> module pulls in its own `lib`. If you get "undefined variable lib", add
> `lib` to the `{ config, pkgs, lib, ... }:` parameter list.

### 3. Rebuild + arm the timer

```bash
sudo nixos-rebuild switch

# confirm the timer is armed:
systemctl list-timers tracker-checkin
```

### 4. Verify it checks in

```bash
# force one immediately:
systemctl start tracker-checkin

# confirm it ran clean:
journalctl -u tracker-checkin --since today
```

### 5. See it on the dashboard

Open `https://track.gooseysserver.eu` **from your LAN** (the GUI is LAN-only),
enter the token once, and both machines should appear with a map pin.

## Options

| Option | Default | Description |
|---|---|---|
| `services.device-tracker.enable` | false | Enable the client |
| `services.device-tracker.server` | `https://track.gooseysserver.eu` | Server URL |
| `services.device-tracker.token` | "" | This device's auth token (one per device) |
| `services.device-tracker.intervalSec` | 300 | Checkin interval (sec) |

## What it reports

- `device_id` (hostname by default, override with `--id`)
- hostname, user, IP
- OS / kernel / arch
- CPU model + 1-min load
- memory (total / available), disk (used / total)
- uptime, boot id (changes each boot — handy for reboot/dual-boot detection)
- battery % + charging state (auto-detects `BAT0/BAT1/BAT2`)

## Manual run (debug)

```bash
python3 nix/tracker-client.py --once \
  --server https://track.gooseysserver.eu \
  --token YOUR-TOKEN
```

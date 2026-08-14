# device-tracker client (NixOS)

Self-hosted device tracking. This is the **client** side — a small stdlib-only
Python script + a systemd timer that reports a checkin (hostname, IP, OS, CPU,
memory, disk, battery, boot id) to your own server every few minutes.

The server (Flask dashboard + geo-IP map) runs on your homeserver and is
reachable at `https://track.gooseysserver.eu`. The dashboard/GUI is LAN-only;
the checkin endpoint is public so machines report in from anywhere.

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

  # Enable the tracker client with your token:
  services.device-tracker = {
    enable = true;
    token = "8b722c…c605";   # your shared token (X-Track-Token)
    # server defaults to https://track.gooseysserver.eu
    # intervalSec defaults to 300 (5 min)
  };
}
```

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
| `services.device-tracker.token` | "" | Shared auth token |
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

#!/usr/bin/env python3
"""
device-tracker client
=====================
Runs on the Framework 12 (or any machine) and reports a lightweight
checkin to your tracking server.  Stdlib-only, so it needs no pip
installs and survives reboots cleanly.

Reported fields:
  device_id   - stable ID (hostname by default, override with --id)
  hostname, user
  ip          - primary non-loopback IPv4
  os / kernel / arch
  cpu model, cpu load (1m avg)
  mem_total / mem_avail
  disk_used / disk_total (root fs)
  uptime (seconds)
  battery_pct (if readable) + charging state
  boot_id     - changes each boot, handy to detect reboot/dual-boot

POSTs to SERVER/api/checkin with header  X-Track-Token: <TOKEN>
Best-effort: any failure is swallowed and retried with backoff.
"""

import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error

CONFIG = {
    # Change these, or pass --server / --token on the command line.
    "server": os.environ.get("TRACK_SERVER", "https://track.gooseysserver.eu"),
    "token":  os.environ.get("TRACK_TOKEN", "change-me-to-a-long-random-string"),
    "timeout": 10,          # seconds
    "retries": 3,
    "backoff": 2,           # base seconds, doubles each retry
}


def _read(path):
    """Read a file, return stripped content or None."""
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _run(cmd):
    """Run a command, return stdout stripped or None."""
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=5
        ).stdout.strip()
    except Exception:
        return None


def primary_ip():
    """Best-effort primary non-loopback IPv4 via UDP connect trick (no traffic sent)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))   # no packets are actually sent
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def meminfo():
    try:
        with open("/proc/meminfo") as f:
            data = {}
            for line in f:
                k, _, v = line.partition(":")
                data[k.strip()] = v.strip().split()[0]
        return {
            "mem_total_kb": int(data.get("MemTotal", 0)),
            "mem_avail_kb": int(data.get("MemAvailable", 0)),
        }
    except Exception:
        return {"mem_total_kb": None, "mem_avail_kb": None}


def disk_usage():
    st = os.statvfs("/")
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    return {"disk_total": total, "disk_free": free}


def loadavg():
    try:
        return float(open("/proc/loadavg").read().split()[0])
    except Exception:
        return None


def uptime():
    try:
        return float(open("/proc/uptime").read().split()[0])
    except Exception:
        return None


def boot_id():
    return _read("/proc/sys/kernel/random/boot_id")


def battery():
    """Framework 12 exposes a battery under /sys/class/power_supply/BAT?."""
    for base in ("/sys/class/power_supply/BAT0",
                 "/sys/class/power_supply/BAT1",
                 "/sys/class/power_supply/BAT2"):
        if os.path.isdir(base):
            def r(n):
                return _read(os.path.join(base, n))
            cap = r("capacity")
            try:
                cap = int(cap) if cap else None
            except ValueError:
                cap = None
            return {
                "battery_pct": cap,
                "charging": r("status"),
                "present": r("present"),
            }
    return {}


def collect(args):
    uname = platform.uname()
    cpu_model = _run(["sh", "-c", "grep -m1 'model name' /proc/cpuinfo | cut -d: -f2- | xargs"])
    return {
        "device_id": args.id or socket.gethostname(),
        "hostname": socket.gethostname(),
        "user": os.environ.get("USER") or os.environ.get("LOGNAME"),
        "ip": primary_ip(),
        "boot_id": boot_id(),
        "os": f"{uname.system} {uname.release}",
        "kernel": uname.release,
        "arch": uname.machine,
        "cpu": cpu_model,
        "load_1m": loadavg(),
        **meminfo(),
        **disk_usage(),
        "uptime_s": uptime(),
        "battery": battery(),
        "ts": time.time(),
    }


def send(url, token, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Track-Token": token,
            "User-Agent": "device-tracker-client/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=CONFIG["timeout"]) as resp:
        return resp.status, resp.read().decode()


def main():
    ap = argparse.ArgumentParser(description="device-tracker client")
    ap.add_argument("--server", default=CONFIG["server"])
    ap.add_argument("--token", default=CONFIG["token"])
    ap.add_argument("--id", default=None,
                    help="stable device id (default: hostname)")
    ap.add_argument("--once", action="store_true",
                    help="send one checkin and exit (default)")
    args = ap.parse_args()

    payload = collect(args)
    url = args.server.rstrip("/") + "/api/checkin"
    token = args.token

    last_err = None
    for attempt in range(CONFIG["retries"]):
        try:
            status, text = send(url, token, payload)
            if status == 200:
                if not args.once:
                    print(f"checkin ok ({payload['device_id']}) -> {url}")
                return 0
            last_err = f"HTTP {status}: {text}"
        except (urllib.error.URLError, OSError, ValueError) as e:
            last_err = str(e)
        time.sleep(CONFIG["backoff"] * (2 ** attempt))

    # Only spam stderr if we actually failed; systemd timer logs this.
    print(f"tracker-client: checkin FAILED: {last_err}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

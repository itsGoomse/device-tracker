#!/usr/bin/env python3
"""geo-test: run the tracker's GeoClue2 flow with a persistent DBus connection,
attaching a main loop (GetClient is async and requires one)."""
import dbus
import dbus.mainloop.glib
import sys
import time
from gi.repository import GLib

BUS_NAME = "org.freedesktop.GeoClue2"
MGR_PATH = "/org/freedesktop/GeoClue2/Manager"
DESKTOP_ID = "com.gooseys.device-tracker"

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
loop = GLib.MainLoop()

def main():
    bus = dbus.SystemBus()

    # 1) Get a client object (dynamic path, async -> needs main loop)
    mgr = bus.get_object(BUS_NAME, MGR_PATH, follow_name_owner_changes=True)
    mgr_iface = dbus.Interface(mgr, "org.freedesktop.GeoClue2.Manager")
    try:
        client_path = mgr_iface.GetClient()
        print("[1] client path:", client_path)
    except Exception as e:
        print("[1] FAILED Manager.GetClient:", e)
        sys.exit(1)

    # 2) Declare our desktop ID so geoclue can authorize us
    client = bus.get_object(BUS_NAME, client_path, follow_name_owner_changes=True)
    ci = dbus.Interface(client, "org.freedesktop.GeoClue2.Client")
    try:
        ci.SetDesktopId(DESKTOP_ID)
        print("[2] SetDesktopId ok:", DESKTOP_ID)
    except Exception as e:
        print("[2] SetDesktopId error:", e)

    # 3) Start the client
    try:
        ci.Start()
        print("[3] Start() ok")
    except Exception as e:
        print("[3] Start() error:", e)

    # 4) Poll for a location fix (async; may take seconds)
    for i in range(6):
        try:
            loc_path = ci.GetLocation()
        except Exception as e:
            loc_path = None
            print(f"[4] try {i+1}: GetLocation error: {e}")
        if loc_path:
            try:
                loc = bus.get_object(BUS_NAME, loc_path)
                props = dbus.Interface(loc, "org.freedesktop.DBus.Properties")
                allp = props.GetAll("org.freedesktop.GeoClue2.Location")
                print("[4] LOCATION:", dict(allp))
                lat = float(allp.get("Latitude", 0))
                lon = float(allp.get("Longitude", 0))
                if lat == 0.0 and lon == 0.0:
                    print("    (lat/lon are 0.0 — no real fix)")
                return
            except Exception as e:
                print("[4] reading location failed:", e)
        time.sleep(1)

    print("[4] NO LOCATION after polling. geoclue returned no fix.")

if __name__ == "__main__":
    main()

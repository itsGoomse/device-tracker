#!/usr/bin/env python3
"""geo-test: run the tracker's GeoClue2 flow with a persistent DBus connection,
using the CORRECT property-based API (DesktopId and Location are properties,
not methods)."""
import dbus
import dbus.mainloop.glib
import sys
import time
from gi.repository import GLib

BUS_NAME = "org.freedesktop.GeoClue2"
MGR_PATH = "/org/freedesktop/GeoClue2/Manager"
DESKTOP_ID = "com.gooseys.device-tracker"
IFACE_CLIENT = "org.freedesktop.GeoClue2.Client"
IFACE_LOC = "org.freedesktop.GeoClue2.Location"

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

def main():
    bus = dbus.SystemBus()

    # 1) Get a client object (dynamic path)
    try:
        mgr = bus.get_object(BUS_NAME, MGR_PATH, follow_name_owner_changes=True)
        mgr_iface = dbus.Interface(mgr, "org.freedesktop.GeoClue2.Manager")
        client_path = mgr_iface.GetClient()
        print("[1] client path:", client_path)
    except Exception as e:
        print("[1] FAILED Manager.GetClient:", e)
        sys.exit(1)

    client = bus.get_object(BUS_NAME, client_path, follow_name_owner_changes=True)
    props = dbus.Interface(client, "org.freedesktop.DBus.Properties")

    # 2) Set the DesktopId PROPERTY (this is how geoclue identifies us)
    try:
        props.Set(IFACE_CLIENT, "DesktopId", DESKTOP_ID)
        print("[2] set DesktopId property:", DESKTOP_ID)
    except Exception as e:
        print("[2] set DesktopId error:", e)

    # 3) Start the client
    try:
        ci = dbus.Interface(client, IFACE_CLIENT)
        ci.Start()
        print("[3] Start() ok")
    except Exception as e:
        print("[3] Start() error:", e)

    # 4) Poll the Location PROPERTY (returns object path when a fix exists)
    for i in range(6):
        try:
            loc_path = props.Get(IFACE_CLIENT, "Location")
        except Exception as e:
            loc_path = dbus.ObjectPath("/")
            print(f"[4] try {i+1}: Location prop error: {e}")
        if loc_path and str(loc_path) != "/":
            try:
                loc = bus.get_object(BUS_NAME, loc_path)
                lprops = dbus.Interface(loc, "org.freedesktop.DBus.Properties")
                allp = lprops.GetAll(IFACE_LOC)
                print("[4] LOCATION:", dict(allp))
                lat = float(allp.get("Latitude", 0))
                lon = float(allp.get("Longitude", 0))
                if lat == 0.0 and lon == 0.0:
                    print("    (lat/lon are 0.0 — no real fix)")
                return
            except Exception as e:
                print("[4] reading location failed:", e)
        else:
            print(f"[4] try {i+1}: Location property empty (no fix yet)")
        time.sleep(1)

    print("[4] NO LOCATION after polling. geoclue returned no fix.")

if __name__ == "__main__":
    main()

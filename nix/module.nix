# NixOS module — device-tracker client.
#
# Self-contained: the client script is baked into this module, so it works
# from anywhere you clone it — no fragile absolute paths.
#
# Usage (classic configuration.nix):
#   1. Clone this repo somewhere on the target machine, e.g. ~/device-tracker.
#   2. In configuration.nix:
#        imports = [ /home/youruser/device-tracker/nix/module.nix ];
#      Or, if you keep configs in a folder, point at the file directly.
#   3. Set the token (below or via the module options).
#   4. sudo nixos-rebuild switch
#
# It installs the script + a systemd timer that checks in every ~5 minutes.

{ config, pkgs, lib, ... }:

let
  # Bake the client script into the derivation so the module is standalone.
  client = pkgs.writeScript "tracker-client.py" (builtins.readFile ./tracker-client.py);
  # Python interpreter with dbus-python + pygobject3 so the client can hold a
  # persistent D-Bus connection to GeoClue2 and run a GLib main loop
  # (required for location).
  trackerPython = pkgs.python3.withPackages (p: [ p.dbus-python p.pygobject3 ]);
in
{
  options.services.device-tracker = {
    enable = lib.mkEnableOption "device-tracker client";
    server = lib.mkOption {
      type = lib.types.str;
      default = "https://track.gooseysserver.eu";
      description = "Tracker server URL.";
    };
    token = lib.mkOption {
      type = lib.types.str;
      default = "";
      description = "Shared auth token (X-Track-Token).";
    };
    intervalSec = lib.mkOption {
      type = lib.types.int;
      default = 300;
      description = "Checkin interval in seconds (default 5 min).";
    };
    deviceId = lib.mkOption {
      type = lib.types.str;
      default = "";
      description = "Stable device ID. Defaults to hostname; set this to a unique per-machine value (e.g. p14s, fw12) so machines with the same hostname don't collide on the server.";
    };
  };

  config = lib.mkIf config.services.device-tracker.enable {
    # GeoClue2 provides location (WiFi/network positioning — no GPS chip
    # needed on these laptops). We whitelist the tracker app directly
    # (appConfig) so no desktop portal/agent authorization is required.
    services.geoclue2 = {
      enable = true;
      # Our client is a system component (isSystem=true below), so it does
      # NOT need the demo agent to authorize it. In fact the demo agent
      # interferes — it only auto-approves known interactive apps and won't
      # authorize a service-context request, which is why the checkin got
      # "no location object after polling" while the interactive test worked.
      # Disable it so the isSystem client talks to geoclue directly.
      enableDemoAgent = false;
      appConfig."com.gooseys.device-tracker" = {
        isAllowed = true;
        isSystem = true;
      };
    };

    # geoclue is DBus-activated and can sit inactive (loaded but never
    # started) — the tracker then gets no location. Force it to start at
    # boot so the client always has a location service to call.
    systemd.services.geoclue.wantedBy = [ "multi-user.target" ];

    # Run the checkin as a USER service (systemd --user), NOT a system
    # service. The geoclue demo agent is a user service inside the desktop
    # session; a system service (even with User=inuk) is outside that
    # session bus, so the agent can't authorize the location request and
    # geoclue returns no fix. A user service shares the session where the
    # agent lives.
    systemd.user.services.tracker-checkin = {
      description = "device-tracker periodic checkin";
      wants = [ "network-online.target" ];
      after = [ "network-online.target" ];
      path = [ pkgs.glib.bin ];
      serviceConfig = {
        Type = "oneshot";
        # ONE string, so systemd parses it as a single command.
        ExecStart =
          "${trackerPython}/bin/python3 ${client} --once"
          + lib.optionalString (config.services.device-tracker.deviceId != "")
            " --id ${config.services.device-tracker.deviceId}";
        Environment = [
          "TRACK_SERVER=${config.services.device-tracker.server}"
          "TRACK_TOKEN=${config.services.device-tracker.token}"
        ];
      };
    };

    systemd.user.timers.tracker-checkin = {
      description = "device-tracker checkin timer";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "30s";
        OnUnitActiveSec = config.services.device-tracker.intervalSec;
        RandomizedDelaySec = "60";
        Persistent = true;
      };
    };
  };
}

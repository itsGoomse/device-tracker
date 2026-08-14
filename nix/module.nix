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
    # needed on these laptops). The client reads it via gdbus on the SYSTEM
    # bus. We whitelist the tracker app directly (appConfig) so no desktop
    # portal/agent authorization is required — this is what makes it work
    # on BOTH KDE Plasma and bare Hyprland (which has no portal agent).
    services.geoclue2 = {
      enable = true;
      appConfig."com.gooseys.device-tracker" = {
        isAllowed = true;
        isSystem = true;
      };
    };

    # geoclue is DBus-activated and can sit inactive (loaded but never
    # started) — the tracker then gets no location. Force it to start at
    # boot so the client always has a location service to call.
    systemd.services.geoclue.wantedBy = [ "multi-user.target" ];

    systemd.services.tracker-checkin = {
      description = "device-tracker periodic checkin";
      wantedBy = [ "timers.target" ];
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      # python3 runs the script; glib.bin provides gdbus (needed to talk to
      # GeoClue2 for location).
      path = [ pkgs.python3 pkgs.glib.bin ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = [
          "${pkgs.python3}/bin/python3 ${client} --once"
        ] ++ lib.optionals (config.services.device-tracker.deviceId != "") [
          "--id ${config.services.device-tracker.deviceId}"
        ];
        Environment = [
          "TRACK_SERVER=${config.services.device-tracker.server}"
          "TRACK_TOKEN=${config.services.device-tracker.token}"
        ];
      };
    };

    systemd.timers.tracker-checkin = {
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

#!/usr/bin/env bash
# geo-diagnose — run the exact GeoClue2 flow the tracker client uses,
# but with ALL error output visible, so we can see where it fails.
# Run AS YOUR USER (inuk) in your normal terminal, NOT in nix-shell.

set +e
GB="gdbus call --system --dest org.freedesktop.GeoClue2"

echo "=== 1) Is the geoclue demo agent running (user service)? ==="
systemctl --user status geoclue-agent --no-pager 2>&1 | head -4

echo
echo "=== 2) Manager.GetClient ==="
MGR=$($GB --object-path /org/freedesktop/GeoClue2/Manager \
          --method org.freedesktop.GeoClue2.Manager.GetClient 2>&1)
echo "raw: $MGR"

CLIENT=$(echo "$MGR" | grep -oE '/org/freedesktop/GeoClue2/Client/[0-9]+')
echo "client path: ${CLIENT:-NONE}"
[ -z "$CLIENT" ] && { echo ">> FAILED to get client object"; exit 1; }

echo
echo "=== 3) SetDesktopId ==="
$GB --object-path "$CLIENT" \
    --method org.freedesktop.GeoClue2.Client.SetDesktopId \
    com.gooseys.device-tracker 2>&1

echo
echo "=== 4) Start() ==="
$GB --object-path "$CLIENT" \
    --method org.freedesktop.GeoClue2.Client.Start 2>&1

echo
echo "=== 5) Poll GetLocation (5 tries, 1s apart) ==="
LOC=""
for i in 1 2 3 4 5; do
  OUT=$($GB --object-path "$CLIENT" \
        --method org.freedesktop.GeoClue2.Client.GetLocation 2>&1)
  echo "try $i: $OUT"
  LOC=$(echo "$OUT" | grep -oE '/org/freedesktop/GeoClue2/Location/[0-9]+')
  [ -n "$LOC" ] && break
  sleep 1
done

echo "location path: ${LOC:-NONE}"
[ -z "$LOC" ] && { echo ">> geoclue never returned a location object"; exit 1; }

echo
echo "=== 6) Read lat/lon ==="
$GB --object-path "$LOC" \
    --method org.freedesktop.DBus.Properties.GetAll \
    org.freedesktop.GeoClue2.Location 2>&1

echo
echo "=== 7) geoclue daemon log (last 15) ==="
journalctl -u geoclue --since "3 min ago" --no-pager 2>&1 | tail -15

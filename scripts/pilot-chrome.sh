#!/usr/bin/env bash
# The Pilot's Chrome (PM2 frameflow-chrome): wait for the desktop's X display, then start Chrome in its place.
# At boot PM2 is up before the login screen hands over the display; Chrome then exits ("Missing X server or $DISPLAY")
# and PM2's restart budget runs out on a slow boot (28 Oct: 5 restarts before the display came up).
# Usage: scripts/pilot-chrome.sh <chrome args...>   (DISPLAY and XAUTHORITY from the PM2 env)
set -uo pipefail
for _ in $(seq 1 120); do   # up to 10 min
  xset q >/dev/null 2>&1 && exec /usr/bin/google-chrome "$@"
  sleep 5
done
echo "pilot-chrome: no X display on ${DISPLAY:-unset} after 10 min" >&2
exit 1

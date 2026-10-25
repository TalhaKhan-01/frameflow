#!/usr/bin/env bash
# Wait for the Vercel production deployment of local HEAD (personal account talha-785b) and check the live site.
# Usage: scripts/deploy-check.sh studio|betadoc   (after git push)
set -euo pipefail
CFG="$HOME/.config/vercel-personal/auth.json"
TEAM=team_fds98RHa6xySDTWPlaNGxqcp
case "${1:-studio}" in
  studio)  PROJECT=frameflow-studio;  SNAP=$(python3 -c "import json;print('studio.json' if json.load(open('web/access.json')).get('open') else 'studio.enc')" 2>/dev/null || echo studio.enc); PATHS="/ /data/$SNAP /media/2026-10-25-black-october/preview.mp4" ;;
  betadoc) PROJECT=frameflow-betadoc; PATHS="/ /documentation.html /live.json /media/latest/preview.mp4 /video/frameflow-tour.mp4 /video/frameflow-tour.vtt" ;;
  *) echo "usage: $0 studio|betadoc"; exit 2 ;;
esac
vercel --global-config "$HOME/.config/vercel-personal" whoami >/dev/null 2>&1 || true   # refreshes an expired token
TOKEN=$(python3 -c "import json;print(json.load(open('$CFG'))['token'])")
HEAD=$(git rev-parse HEAD)
[ -z "$(git status --porcelain)" ] || { echo "working tree not clean"; exit 1; }
[ -z "$(git log origin/main..HEAD --oneline)" ] || { echo "HEAD not pushed"; exit 1; }
LIVE=""
for i in $(seq 1 60); do
  R=$(curl -s "https://api.vercel.com/v6/deployments?teamId=$TEAM&projectId=$PROJECT&target=production&limit=10" -H "Authorization: Bearer $TOKEN" \
    | python3 -c "import json,sys;h='$HEAD';d=[x for x in json.load(sys.stdin)['deployments'] if x['meta'].get('githubCommitSha')==h];print(d[0]['state'] if d else 'WAITING')")
  echo "deployment for ${HEAD:0:12}: $R"
  case "$R" in READY) break;; ERROR|CANCELED) exit 1;; esac
  sleep 10
done
[ "$R" = READY ] || exit 1
LIVE=$(curl -s "https://api.vercel.com/v9/projects/$PROJECT?teamId=$TEAM" -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import json,sys;a=json.load(sys.stdin)['targets']['production']['alias'];print('https://'+min(a,key=len))")
for p in $PATHS; do code=$(curl -s -o /dev/null -w '%{http_code}' "$LIVE$p"); echo "$LIVE$p $code"; [ "$code" = 200 ] || exit 1; done
echo "LIVE OK: $LIVE serves ${HEAD:0:12}"

#!/usr/bin/env bash
# Start the whole Pak Imtehan poster flow locally inside herdr:
#
#   tab "stack":  pi_user_server (:4000) | dashboard (:5174) | website (:5173)
#   tab "posters": a shell in this repo (run `claude`, or `python build.py ...`)
#
# Nothing here edits the projects' .env files: every local override is passed on
# the command line, which beats .env for both Node (dotenv) and Vite.
#
# Usage:  scripts/local-stack.sh            (starts herdr's server if needed, then attach with `herdr`)
set -euo pipefail

GH_DIR="${GH_DIR:-$HOME/Documents/GitHub}"
SERVER_DIR="$GH_DIR/pi_user_server"
DASH_DIR="$GH_DIR/pi_user_dashboard"
WEB_DIR="$GH_DIR/pak-imtehan-website"
POSTERS_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Posters wait in the Cloudflare Worker "pakimtehan-posters" (D1). Its URL and token are read from
# ~/.config/pakimtehan-posters/store.env (mode 600, never committed):
#   NEWS_POSTERS_STORE_URL=https://pakimtehan-posters.<subdomain>.workers.dev
#   NEWS_POSTERS_STORE_TOKEN=<the Worker secret STORE_TOKEN>
STORE_ENV="$HOME/.config/pakimtehan-posters/store.env"
[ -f "$STORE_ENV" ] || { echo "Missing $STORE_ENV (poster storage URL and token)"; exit 1; }
# shellcheck disable=SC1090
. "$STORE_ENV"

# DISABLE_SUBSCRIPTION_CRON=true keeps the subscription-expiry cron (Firestore writes)
# off on this laptop, even if pi_user_server/.env loses the line.

json() { python3 -c "import json,sys; d=json.load(sys.stdin); print(eval('d'+sys.argv[1]))" "$1"; }

if ! herdr status server 2>/dev/null | grep -q "status: running"; then
  echo "Starting herdr server in the background..."
  # `herdr server` runs herdr headless; it keeps running after this terminal closes.
  (setsid herdr server >/dev/null 2>&1 < /dev/null &) || true
  for _ in $(seq 1 40); do herdr status server 2>/dev/null | grep -q "status: running" && break; sleep 0.25; done
fi

ws=$(herdr workspace create --cwd "$SERVER_DIR" --label "pak-imtehan-local" --no-focus)
server_pane=$(printf '%s' "$ws" | json "['result']['root_pane']['pane_id']")
dash_pane=$(herdr pane split "$server_pane" --direction right --cwd "$DASH_DIR" --no-focus | json "['result']['pane']['pane_id']")
web_pane=$(herdr pane split "$dash_pane" --direction down --cwd "$WEB_DIR" --no-focus | json "['result']['pane']['pane_id']")

herdr pane run "$server_pane" "DISABLE_SUBSCRIPTION_CRON=true PORT=4000 ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174 NEWS_POSTERS_STORE_URL=$NEWS_POSTERS_STORE_URL NEWS_POSTERS_STORE_TOKEN=$NEWS_POSTERS_STORE_TOKEN NEWS_POSTERS_SYNC_CRON='*/5 * * * *' npm start" >/dev/null
herdr pane run "$dash_pane" "VITE_API_URL=/ DASHBOARD_API_PROXY=http://localhost:4000 npx vite --port 5174 --strictPort" >/dev/null
herdr pane run "$web_pane" "VITE_PI_SERVER_URL=http://localhost:4000/api/v3 npx vite --port 5173 --strictPort" >/dev/null

ws_id=$(printf '%s' "$ws" | json "['result']['workspace']['workspace_id']")
herdr tab create --workspace "$ws_id" --cwd "$POSTERS_DIR" --label posters >/dev/null 2>&1 \
  || herdr tab create --workspace "$ws_id" >/dev/null 2>&1 || true

cat <<EOF

Pak Imtehan local stack is starting in herdr workspace "pak-imtehan-local".
  Server     http://localhost:4000/health   (syncs posters from GitHub now and every 5 min)
  Dashboard  http://localhost:5174/posters  (sign in with a local admin account)
  Website    http://localhost:5173/current-affairs

Attach to watch the logs:  herdr
Stop everything:           herdr workspace close $ws_id
EOF

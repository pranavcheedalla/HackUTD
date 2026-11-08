#!/bin/bash
# NorthBound demo, one double-click: starts the local server (if it isn't already running)
# and opens the slides. Keep this window open while presenting; close it to stop the server.
cd "$(dirname "$0")/.." || exit 1
PORT=8765
URL="http://127.0.0.1:$PORT"
PY=../backend-venv/bin/python
[ -x "$PY" ] || PY=.venv/bin/python
[ -x "$PY" ] || PY=python3

if curl -sf "$URL/api/status" >/dev/null; then
  echo "NorthBound is already running at $URL"
else
  echo "Starting NorthBound at $URL ..."
  "$PY" tools/serve.py --port "$PORT" &
  SERVER=$!
  trap 'kill $SERVER 2>/dev/null' EXIT
  for _ in $(seq 60); do curl -sf "$URL/api/status" >/dev/null && break; sleep 0.25; done
fi

curl -s "$URL/api/status" | grep -q '"live": true' && echo "Live runs: ON (NVIDIA_API_KEY found)" \
  || echo "Live runs: OFF (no NVIDIA_API_KEY in .env). Slides and the recorded demo still work."
open "$URL/deck.html"
echo
echo "Slides: $URL/deck.html   (→ to move; slide 2's Next goes into NorthBound; press C there for slide 3)"
echo "Keep this window open during the demo. Close it (or press Ctrl+C) to stop."
[ -n "$SERVER" ] && wait "$SERVER" || read -r -p "Press Enter to close this window..."

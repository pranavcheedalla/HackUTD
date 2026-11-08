#!/usr/bin/env bash
# The guaranteed human-feedback demo (offline: real pipeline and real GnuCOBOL, canned agent answers).
# INVOICE fails 3 attempts in a few seconds, then waits for a person in the galaxy's "Needs a person"
# panel; any feedback gives it 2 more attempts and attempt 4 passes 15/15.
#
#   REVIEW_WAIT=300 python tools/serve.py     # first, in another terminal
#   tools/demo_feedback.sh                    # then this; it opens the page
#
# Env: PORT (8765), REVIEW_WAIT (300 s the stuck program waits for feedback).
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${PORT:-8765}"
PY="${PYTHON:-.venv/bin/python}"
[ -x "$PY" ] || PY=python3

if ! curl -sf "http://127.0.0.1:$PORT/api/status" >/dev/null; then
  echo "The galaxy server is not running on port $PORT. Start it first:" >&2
  echo "  REVIEW_WAIT=300 $PY tools/serve.py" >&2
  exit 1
fi

latest=runs/latest_session.json
before="$(cat "$latest" 2>/dev/null || true)"
mkdir -p runs
DEMO_SCENARIO=review REVIEW_WAIT="${REVIEW_WAIT:-300}" \
  nohup "$PY" tools/isolated_run.py --mode fake --only invoice >runs/demo-feedback.log 2>&1 &
pid=$!

session=""
for _ in $(seq 60); do  # isolated_run publishes its session name right after copying the repo
  sleep 0.25
  if ! kill -0 "$pid" 2>/dev/null; then break; fi
  now="$(cat "$latest" 2>/dev/null || true)"
  if [ -n "$now" ] && [ "$now" != "$before" ]; then
    session="$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["session"])' "$latest")"
    break
  fi
done
if [ -z "$session" ]; then
  echo "The demo run did not start. Last lines of runs/demo-feedback.log:" >&2
  tail -5 runs/demo-feedback.log >&2
  exit 1
fi

url="http://127.0.0.1:$PORT/#live=$session"
echo "Offline feedback demo: $url"
echo "INVOICE asks for help in about 10 s. Type e.g.: fractions of a cent are cut off, never rounded"
command -v open >/dev/null && open "$url" || true

#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-9223}"
PROFILE="${PROFILE:-Default}"
URL="${URL:-about:blank}"
SESSION="${SESSION:-canary-profile-$PORT}"
CANARY_APP="${CANARY_APP:-Google Chrome Canary}"
CONNECT_AGENT_BROWSER="${CONNECT_AGENT_BROWSER:-0}"
CHROME_ROOT="${CHROME_ROOT:-$HOME/Library/Application Support/Google/Chrome}"
SRC_ROOT="$CHROME_ROOT"
SRC_PROFILE="$SRC_ROOT/$PROFILE"
SRC_LOCAL_STATE="$SRC_ROOT/Local State"
CLONE_ROOT="${CLONE_ROOT:-$HOME/chrome-agent-profile}"
CLONE_DIR="$CLONE_ROOT/$PROFILE"
COPY_SOURCE_PROFILE="${COPY_SOURCE_PROFILE:-0}"

if ! /usr/bin/open -Ra "$CANARY_APP" >/dev/null 2>&1; then
  echo "missing Chrome Canary app: $CANARY_APP" >&2
  exit 1
fi

if curl -fsS --max-time 1 "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1; then
  echo "Chrome Canary/CDP already listening on $PORT"
  if [[ "$CONNECT_AGENT_BROWSER" == "1" ]]; then
    AGENT_BROWSER_SESSION="$SESSION" agent-browser --cdp "$PORT" connect "$PORT"
  fi
  exit 0
fi

mkdir -p "$CLONE_ROOT" "$CLONE_DIR"

rm -f \
  "$CLONE_ROOT"/Singleton* \
  "$CLONE_ROOT"/LOCK \
  "$CLONE_ROOT"/.org.chromium.Chromium.* \
  "$CLONE_DIR"/Singleton* \
  "$CLONE_DIR"/LOCK \
  "$CLONE_DIR"/.org.chromium.Chromium.* 2>/dev/null || true

if [[ "$COPY_SOURCE_PROFILE" == "1" ]]; then
  if [[ -f "$SRC_LOCAL_STATE" && ! -f "$CLONE_ROOT/Local State" ]]; then
    cp "$SRC_LOCAL_STATE" "$CLONE_ROOT/Local State" 2>/dev/null || true
  fi

  if [[ -d "$SRC_PROFILE" ]]; then
    if ! rsync -a --delete \
      --exclude 'Cache/' \
      --exclude 'Code Cache/' \
      --exclude 'GPUCache/' \
      --exclude 'Dawn*Cache/' \
      --exclude 'GrShaderCache/' \
      --exclude 'ShaderCache/' \
      --exclude 'BrowserMetrics/' \
      --exclude 'Crashpad/' \
      --exclude 'LOCK' \
      --exclude 'Singleton*' \
      --exclude '.org.chromium.Chromium.*' \
      "$SRC_PROFILE/" "$CLONE_DIR/"; then
      echo "warning: cannot clone source profile, using existing Canary profile: $SRC_PROFILE" >&2
    fi
  else
    echo "warning: missing source profile, using existing Canary profile: $SRC_PROFILE" >&2
  fi
fi

/usr/bin/open -na "$CANARY_APP" --args \
  --remote-debugging-port="$PORT" \
  --remote-allow-origins="http://127.0.0.1:$PORT" \
  --user-data-dir="$CLONE_ROOT" \
  --profile-directory="$PROFILE" \
  --no-first-run \
  --no-default-browser-check \
  "$URL" >/tmp/canary-profile-browser.log 2>&1

for _ in {1..80}; do
  if curl -fsS --max-time 1 "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1; then
    echo "Chrome Canary/CDP listening on $PORT"
    if [[ "$CONNECT_AGENT_BROWSER" == "1" ]]; then
      AGENT_BROWSER_SESSION="$SESSION" agent-browser --cdp "$PORT" connect "$PORT"
    fi
    exit 0
  fi
  sleep 0.25
done

echo "failed to start Chrome Canary on port $PORT; see /tmp/canary-profile-browser.log" >&2
exit 1

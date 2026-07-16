#!/usr/bin/env bash
# 启动 Chrome Canary 并开启 CDP 调试端口
# 用途：让 agent-browser 通过 --cdp 9222 接管浏览器，profile 与日常 Chrome 完全隔离

set -euo pipefail

CDP_PORT="${CDP_PORT:-9222}"
PROFILE_DIR="${PROFILE_DIR:-/Users/bytedance/chrome-agent-profile}"
CANARY_BIN="${CANARY_BIN:-/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary}"
LOG_FILE="${LOG_FILE:-/tmp/canary-cdp.log}"

print_version() {
  curl -s "http://localhost:${CDP_PORT}/json/version" | head -c 200
  echo
}

# 1. 已经在跑就直接返回
if curl -sf "http://localhost:${CDP_PORT}/json/version" > /dev/null 2>&1; then
  echo "Canary already running on port ${CDP_PORT}"
  print_version
  exit 0
fi

# 2. 检查 Canary 是否已安装
if [[ ! -x "${CANARY_BIN}" ]]; then
  echo "ERROR: Canary not found at: ${CANARY_BIN}" >&2
  echo "Install with: brew install --cask google-chrome-canary" >&2
  exit 2
fi

# 3. 准备 profile / log 目录
mkdir -p "${PROFILE_DIR}"
mkdir -p "$(dirname "${LOG_FILE}")"

# 4. 后台启动 Canary，脱离当前 shell session（避免被 agent 进程退出连带杀掉）
nohup "${CANARY_BIN}"   --remote-debugging-port="${CDP_PORT}"   --user-data-dir="${PROFILE_DIR}"   --no-first-run   --no-default-browser-check   > "${LOG_FILE}" 2>&1 &

# 5. 轮询等待 CDP 端口就绪（最多 20 秒）
for i in $(seq 1 20); do
  if curl -sf "http://localhost:${CDP_PORT}/json/version" > /dev/null 2>&1; then
    echo "Canary ready on port ${CDP_PORT} (after ${i}s)"
    print_version
    exit 0
  fi
  sleep 1
done

echo "ERROR: Canary did not become ready within 20s. See ${LOG_FILE}" >&2
tail -20 "${LOG_FILE}" >&2 || true
exit 1

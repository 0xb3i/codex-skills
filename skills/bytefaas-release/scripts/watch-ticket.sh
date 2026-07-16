#!/usr/bin/env bash
# 轮询 ByteFaaS 工单状态，并在进入“全机房灰度”后自动触发节点内“全量”

set -euo pipefail

TICKET_URL="${1:-}"
AB_HOME="${AB_HOME:-/tmp/ab-home}"
CDP_PORT="${CDP_PORT:-9222}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-30}"
MAX_POLLS="${MAX_POLLS:-60}"
HYDRATION_RETRIES="${HYDRATION_RETRIES:-15}"
HYDRATION_WAIT_MS="${HYDRATION_WAIT_MS:-2000}"

if [[ -z "${TICKET_URL}" ]]; then
  echo "USAGE: $0 <ticket_url>" >&2
  exit 2
fi

mkdir -p "${AB_HOME}"

ab() {
  HOME="${AB_HOME}" agent-browser --cdp "${CDP_PORT}" "$@"
}

read_state() {
  ab eval '(() => {
    const nodes = [...document.querySelectorAll(".pipelines-node")].map((node) => ({
      text: (node.innerText || "").trim(),
      cls: String(node.className || ""),
    }));
    const inlineFull = [...document.querySelectorAll("*")].find(
      (el) => (el.innerText || "").trim() === "全量" &&
        el.closest(".pipelines-node") &&
        (el.closest(".pipelines-node").innerText || "").includes("全机房灰度")
    );
    const bannerFullPublishBtn = [...document.querySelectorAll("button")].find(
      (btn) => (btn.innerText || "").trim() === "全量发布"
    );
    const bannerText = [...document.querySelectorAll("*")]
      .map((el) => (el.innerText || "").trim())
      .find((text) => text.startsWith("成功") || text.startsWith("失败") || text.startsWith("进行中")) || "";
    const grayNode = nodes.find((node) => node.text.includes("全机房灰度"));
    const fullNode = nodes.find((node) => node.text.includes("全机房全量"));

    return {
      nodes,
      inlineFullVisible: !!inlineFull,
      bannerFullPublishVisible: !!bannerFullPublishBtn,
      // ponytail: banner button is the wrong control here; click the gray-stage inline action only.
      needsFull: !!inlineFull && !!grayNode && grayNode.cls.includes("loading"),
      fullSuccess: (!!fullNode && fullNode.cls.includes("success")) || bannerText.startsWith("成功"),
      hasError: nodes.some((node) => /error|fail/.test(node.cls)) || bannerText.startsWith("失败"),
      bannerText,
    };
  })()' 2>/dev/null || printf '{}'
}

nodes_empty() {
  grep -Eq '"nodes":[[:space:]]*\[\]'
}

read_state_with_retry() {
  local state
  state="$(read_state)"
  if ! nodes_empty <<<"${state}"; then
    printf '%s' "${state}"
    return
  fi
  local attempt
  for attempt in $(seq 1 "${HYDRATION_RETRIES}"); do
    ab wait "${HYDRATION_WAIT_MS}" >/dev/null 2>&1 || true
    state="$(read_state)"
    if ! nodes_empty <<<"${state}"; then
      break
    fi
  done
  printf '%s' "${state}"
}

click_full_publish() {
  ab eval '(() => {
    const isVisible = (el) => {
      const rect = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
    };
    const target = [...document.querySelectorAll("*")].find((el) => {
      const node = el.closest(".pipelines-node");
      return (el.innerText || "").trim() === "全量" &&
        node &&
        (node.innerText || "").includes("全机房灰度") &&
        String(node.className || "").includes("loading") &&
        isVisible(el);
    });
    if (!target) {
      return "NO_INLINE_FULL";
    }
    target.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
    return "CLICKED_INLINE_FULL";
  })()' 2>/dev/null || true
}

has_error() {
  grep -Eq '"hasError":[[:space:]]*true'
}

has_full_success() {
  grep -Eq '"fullSuccess":[[:space:]]*true'
}

needs_full_publish() {
  grep -Eq '"needsFull":[[:space:]]*true'
}

ab open "${TICKET_URL}" >/dev/null 2>&1 || true
ab wait 2000 >/dev/null 2>&1 || true

empty_polls=0

for i in $(seq 1 "${MAX_POLLS}"); do
  echo "POLL:${i} $(date +%H:%M:%S)"

  state="$(read_state_with_retry)"

  echo "${state}"

  if nodes_empty <<<"${state}"; then
    empty_polls=$((empty_polls + 1))
    if (( empty_polls >= 2 )); then
      echo "REOPEN_AFTER_EMPTY_STATE"
      ab open "${TICKET_URL}" >/dev/null 2>&1 || true
      ab wait 2000 >/dev/null 2>&1 || true
      empty_polls=0
    fi
  else
    empty_polls=0
  fi

  if has_error <<<"${state}"; then
    echo "RESULT:FAILED"
    exit 1
  fi

  if needs_full_publish <<<"${state}"; then
    click_result="$(click_full_publish)"
    echo "${click_result}"
  fi

  if has_full_success <<<"${state}"; then
    echo "RESULT:SUCCESS"
    exit 0
  fi

  sleep "${POLL_INTERVAL_SECONDS}"
done

echo "RESULT:TIMEOUT"
exit 2

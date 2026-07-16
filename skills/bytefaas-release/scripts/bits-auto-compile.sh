#!/usr/bin/env bash
set -euo pipefail

# One-command workflow for Bits pipeline 1168542993666.
# Default branch: debug_ppe
#
# Usage:
#   ./bits-auto-compile-workflow.sh
#   ./bits-auto-compile-workflow.sh feature_branch
#   POLL_SECONDS=15 MAX_POLLS=120 ./bits-auto-compile-workflow.sh debug_ppe
#
# master branch is auto-built by Bits. For master, reuse the active run and
# approve TTP sync; do not trigger another run unless TRIGGER_MASTER=1.

PIPELINE_ID="1168542993666"
SPACE_ID="201141148930"
TTP_JOB_UID="ttp_code_sync_de0a"
BRANCH="${1:-debug_ppe}"
POLL_SECONDS="${POLL_SECONDS:-20}"
MAX_POLLS="${MAX_POLLS:-120}"
REGISTRY="${NPM_CONFIG_REGISTRY:-http://bnpm.byted.org}"
WORK_DIR="${WORK_DIR:-work}"

mkdir -p "$WORK_DIR"

bytedcli() {
  local bytedcli_bin
  bytedcli_bin="$(type -P bytedcli || true)"
  if [[ -n "$bytedcli_bin" ]]; then
    PUPPETEER_SKIP_DOWNLOAD=true "$bytedcli_bin" "$@"
  else
    PUPPETEER_SKIP_DOWNLOAD=true NPM_CONFIG_REGISTRY="$REGISTRY" \
      npx -y @bytedance-dev/bytedcli@latest "$@"
  fi
}

json_string() {
  node -e 'process.stdout.write(JSON.stringify(process.argv[1]))' "$1"
}

branch_vars_json() {
  node -e 'process.stdout.write(JSON.stringify({ branch: process.argv[1] }))' "$1"
}

get_bytecloud_jwt() {
  bytedcli --json auth get-bytecloud-jwt-token | node -e '
let s = "";
process.stdin.on("data", d => s += d);
process.stdin.on("end", () => {
  const parsed = JSON.parse(s);
  if (!parsed.data || !parsed.data.jwt) {
    console.error("missing jwt in auth response");
    process.exit(1);
  }
  process.stdout.write(parsed.data.jwt);
});'
}

get_username() {
  bytedcli --json auth status | node -e '
let s = "";
process.stdin.on("data", d => s += d);
process.stdin.on("end", () => {
  const parsed = JSON.parse(s);
  const username = parsed.data?.bytecloud_auth?.identity?.username || parsed.data?.identity?.username || parsed.data?.username;
  if (!username) {
    console.error("missing username in auth status response");
    process.exit(1);
  }
  process.stdout.write(username);
});'
}

redact_status_file() {
  node - <<'NODE' "$STATUS_FILE"
const fs = require('fs');
const file = process.argv[2];
let text = fs.readFileSync(file, 'utf8');
text = text.replace(/eyJ[a-zA-Z0-9_.-]{20,}/g, '[JWT_REDACTED]');
fs.writeFileSync(file, text);
NODE
}

ensure_auth() {
  local auth_status bits_status
  auth_status="$(bytedcli --json auth status)"
  if ! node -e 'const s=JSON.parse(process.argv[1]); process.exit(s.data && s.data.authenticated ? 0 : 1)' "$auth_status"; then
    echo "ByteCloud auth is not ready. Run: bytedcli auth login --begin" >&2
    exit 1
  fi

  bits_status="$(bytedcli --json bits auth status)"
  if ! node -e 'const s=JSON.parse(process.argv[1]); process.exit(s.cached && !s.expired ? 0 : 1)' "$bits_status"; then
    echo "Bits token missing or expired; refreshing..."
    bytedcli --json bits auth login >/dev/null
  fi
}

trigger_run() {
  local vars_json
  vars_json="$(branch_vars_json "$BRANCH")"
  bytedcli --json bits pipelines run --pipeline-id "$PIPELINE_ID" --vars "$vars_json"
}

find_active_master_run() {
  bytedcli --json bits pipeline "$PIPELINE_ID" \
    --with-job-operations \
    --space-id "$SPACE_ID" | node -e '
let s = "";
process.stdin.on("data", d => s += d);
process.stdin.on("end", () => {
  const root = JSON.parse(s);
  const runs = root.data?.pipelineRuns || [];
  const active = runs.find((run) => {
    const jobs = run.jobs || [];
    if (!jobs.length) return false;
    const ttpSync = jobs.find(j => j.jobId === "ttp_code_sync_de0a");
    const ttpBuild = jobs.find(j => /ICM镜像构建TTP/.test(j.jobName || "") || j.jobId === "icm_build_atomic_ttp_from_cn");
    const interesting = [ttpSync, ttpBuild].filter(Boolean);
    return interesting.some(j => ![14, 15].includes(Number(j.jobStatus)));
  });
  if (!active) process.exit(1);
  process.stdout.write(JSON.stringify({ runSeq: active.runSeq, runId: active.runId }));
});'
}

fetch_status() {
  bytedcli --json bits pipeline "$PIPELINE_ID" \
    --run-seq "$RUN_SEQ" \
    --with-job-operations \
    --space-id "$SPACE_ID"
}

summarize_status() {
  node - <<'NODE' "$STATUS_FILE" "$RUN_SEQ"
const fs = require('fs');
const file = process.argv[2];
const runSeq = process.argv[3];
const root = JSON.parse(fs.readFileSync(file, 'utf8'));
const data = root.data || {};
const run = (data.pipelineRuns || []).find(r => String(r.runSeq) === String(runSeq)) || (data.pipelineRuns || [])[0];
if (!run) {
  console.log('No pipeline run found in status response.');
  process.exit(2);
}
const jobs = (run.jobs || []).map(j => `${j.jobName}:${j.jobStatus}`).join(', ');
console.log(`[poll] runSeq=${run.runSeq} runStatus=${run.runStatus} running=${data.runningCount || 0} blocking=${data.blockingCount || 0} jobs=[${jobs}]`);
NODE
}

extract_ttp_state() {
  node - <<'NODE' "$STATUS_FILE" "$TTP_JOB_UID"
const fs = require('fs');
const file = process.argv[2];
const jobUid = process.argv[3];
const root = JSON.parse(fs.readFileSync(file, 'utf8'));
const run = (root.data?.pipelineRuns || [])[0];
const job = (run?.jobs || []).find(j => j.jobId === jobUid);
if (!run || !job) process.exit(1);
console.log(JSON.stringify({
  runId: run.runId,
  runSeq: run.runSeq,
  runStatus: run.runStatus,
  jobRunId: job.jobRunId,
  jobStatus: job.jobStatus,
  failReason: job.failReason ? JSON.stringify(job.failReason) : ''
}));
NODE
}

approve_ttp_sync() {
  local pipeline_run_id="$1"
  local job_run_id="$2"
  local jwt username
  jwt="$(get_bytecloud_jwt)"
  username="$(get_username)"
  node - <<'NODE' "$jwt" "$pipeline_run_id" "$job_run_id" "$username"
const jwt = process.argv[2];
const pipelineRunId = process.argv[3];
const jobRunId = process.argv[4];
const username = process.argv[5];
const endpoint = `https://bits.bytedance.net/api/v1/p/job_runs/${jobRunId}?pipelineRunId=${pipelineRunId}`;
const payload = {
  operation: 8,
  inputs: {
    jobId: String(jobRunId),
    job_id: Number(jobRunId),
    job: Number(jobRunId),
    index: 'user_define',
    btn_status: 'success',
    method: 'post',
    url: '/api/v1/UserDefinedMethod',
    is_pass: true,
    method_name: 'UserDefinedMethod',
    username,
    __jwt_token__: { cn: jwt }
  }
};
const res = await fetch(endpoint, {
  method: 'POST',
  headers: {
    accept: 'application/json, text/plain, */*',
    'accept-language': 'zh',
    'content-type': 'application/json',
    origin: 'https://bits.bytedance.net',
    referer: 'https://bits.bytedance.net/',
    'x-jwt-token': jwt
  },
  body: JSON.stringify(payload)
});
const text = await res.text();
let body;
try { body = JSON.parse(text); } catch { body = text; }
if (!res.ok) {
  console.error(JSON.stringify({ status: res.status, body }));
  process.exit(1);
}
console.log(JSON.stringify({ ok: true, status: res.status, body }));
NODE
}

retry_ttp_sync() {
  local pipeline_run_id="$1"
  local job_run_id="$2"
  bytedcli --json bits job-run retry \
    --job-run-id "$job_run_id" \
    --pipeline-run-id "$pipeline_run_id" \
    --space-id "$SPACE_ID" \
    --job-uid "$TTP_JOB_UID" >/dev/null
}

is_terminal_success() {
  node - <<'NODE' "$STATUS_FILE" "$RUN_SEQ"
const fs = require('fs');
const root = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const run = (root.data?.pipelineRuns || []).find(r => String(r.runSeq) === String(process.argv[3])) || (root.data?.pipelineRuns || [])[0];
const jobs = run?.jobs || [];
const allDone = jobs.length > 0 && jobs.every(j => Number(j.jobStatus) === 14 || Number(j.jobStatus) === 1);
const anyFailed = jobs.some(j => Number(j.jobStatus) === 15);
process.exit(allDone && !anyFailed ? 0 : 1);
NODE
}

has_failed() {
  node - <<'NODE' "$STATUS_FILE" "$RUN_SEQ"
const fs = require('fs');
const root = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const run = (root.data?.pipelineRuns || []).find(r => String(r.runSeq) === String(process.argv[3])) || (root.data?.pipelineRuns || [])[0];
const jobs = run?.jobs || [];
process.exit(jobs.some(j => Number(j.jobStatus) === 15) ? 0 : 1);
NODE
}

print_final_summary() {
  node - <<'NODE' "$STATUS_FILE" "$RUN_SEQ"
const fs = require('fs');
const root = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const run = (root.data?.pipelineRuns || []).find(r => String(r.runSeq) === String(process.argv[3])) || (root.data?.pipelineRuns || [])[0];
function clean(v) {
  if (!v) return v;
  let s = typeof v === 'string' ? v : JSON.stringify(v);
  s = s.replace(/eyJ[a-zA-Z0-9_.-]{20,}/g, '[JWT_REDACTED]');
  return s.length > 600 ? s.slice(0, 600) + '...' : s;
}
console.log(JSON.stringify({
  runSeq: run?.runSeq,
  runId: run?.runId,
  runStatus: run?.runStatus,
  url: run?.pipelineRunUrl,
  artifacts: (run?.pipelineRunArtifacts || []).map(a => ({ name: a.name, source: a.source, sizeKb: a.sizeKb })),
  jobs: (run?.jobs || []).map(j => ({
    name: j.jobName,
    jobRunId: j.jobRunId,
    status: j.jobStatus,
    startedAt: j.startedAt,
    completedAt: j.completedAt,
    timeCostSec: j.timeCostSec,
    failReason: clean(j.failReason && (j.failReason.message || j.failReason))
  }))
}, null, 2));
NODE
}

echo "== Bits compile workflow =="
echo "pipeline=$PIPELINE_ID space=$SPACE_ID branch=$BRANCH"
ensure_auth

if [[ "$BRANCH" == "master" && "${TRIGGER_MASTER:-}" != "1" ]]; then
  if ! MASTER_RUN="$(find_active_master_run)"; then
    echo "no active master Bits run found; master is auto-built, so not triggering a new run" >&2
    exit 4
  fi
  RUN_ID="$(node -e 'const s=JSON.parse(process.argv[1]); process.stdout.write(String(s.runId))' "$MASTER_RUN")"
  RUN_SEQ="$(node -e 'const s=JSON.parse(process.argv[1]); process.stdout.write(String(s.runSeq))' "$MASTER_RUN")"
  echo "reusing active master runSeq=$RUN_SEQ runId=$RUN_ID"
else
  TRIGGER_RESPONSE="$(trigger_run)"
  RUN_ID="$(node -e 'const s=JSON.parse(process.argv[1]); process.stdout.write(String(s.data.runId))' "$TRIGGER_RESPONSE")"
  RUN_SEQ="$(node -e 'const s=JSON.parse(process.argv[1]); process.stdout.write(String(s.data.runSeq))' "$TRIGGER_RESPONSE")"
  echo "triggered runSeq=$RUN_SEQ runId=$RUN_ID"
fi

STATUS_FILE="$WORK_DIR/bits-auto-compile-${PIPELINE_ID}-${RUN_SEQ}.json"
approved_ttp="false"
retried_after_bad_approval="false"

for ((i = 1; i <= MAX_POLLS; i++)); do
  fetch_status > "$STATUS_FILE"
  redact_status_file
  summarize_status

  if ttp_state_json="$(extract_ttp_state 2>/dev/null)"; then
    ttp_status="$(node -e 'const s=JSON.parse(process.argv[1]); process.stdout.write(String(s.jobStatus))' "$ttp_state_json")"
    ttp_job_run_id="$(node -e 'const s=JSON.parse(process.argv[1]); process.stdout.write(String(s.jobRunId))' "$ttp_state_json")"
    ttp_pipeline_run_id="$(node -e 'const s=JSON.parse(process.argv[1]); process.stdout.write(String(s.runId))' "$ttp_state_json")"
    ttp_fail_reason="$(node -e 'const s=JSON.parse(process.argv[1]); process.stdout.write(String(s.failReason || ""))' "$ttp_state_json")"

    if [[ "$ttp_status" == "4" && "$approved_ttp" != "true" ]]; then
      echo "approving TTP sync jobRunId=$ttp_job_run_id"
      approve_ttp_sync "$ttp_pipeline_run_id" "$ttp_job_run_id" >/dev/null
      approved_ttp="true"
    elif [[ "$ttp_status" == "15" && "$retried_after_bad_approval" != "true" ]]; then
      if [[ "$ttp_fail_reason" == *"__jwt_token__"* || "$ttp_fail_reason" == *"UserDefinedMethod"* ]]; then
        echo "TTP approval failed due to callback/JWT shape; retrying once with known-good payload"
        retry_ttp_sync "$ttp_pipeline_run_id" "$ttp_job_run_id"
        approved_ttp="false"
        retried_after_bad_approval="true"
      fi
    fi
  fi

  if is_terminal_success; then
    echo "workflow completed successfully"
    print_final_summary
    exit 0
  fi

  if has_failed; then
    echo "workflow has failed job(s)"
    print_final_summary
    exit 2
  fi

  sleep "$POLL_SECONDS"
done

echo "workflow timed out after ${MAX_POLLS} polls"
print_final_summary
exit 3

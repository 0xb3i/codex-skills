#!/usr/bin/env bash
# 从 bits 状态 JSON 中只解析 US-TTP / ICM镜像构建TTP 的 image_version。

set -euo pipefail

PIPELINE_ID="${PIPELINE_ID:-1168542993666}"
WORK_DIR="${WORK_DIR:-work}"

STATUS_FILE=""
if [[ "${1:-}" == "--file" ]]; then
  STATUS_FILE="${2:-}"
  if [[ -z "${STATUS_FILE}" ]]; then
    echo "USAGE: $0 --file <status.json>" >&2
    exit 2
  fi
else
  RUN_SEQ="${1:-}"
  if [[ -z "${RUN_SEQ}" ]]; then
    echo "USAGE: $0 <runSeq>" >&2
    exit 2
  fi
  STATUS_FILE="${WORK_DIR}/bits-auto-compile-${PIPELINE_ID}-${RUN_SEQ}.json"
fi

if [[ ! -f "${STATUS_FILE}" ]]; then
  echo "status file not found: ${STATUS_FILE}" >&2
  exit 3
fi

node - "${STATUS_FILE}" <<'NODE'
const fs = require('fs');
const path = process.argv[2];
const root = JSON.parse(fs.readFileSync(path, 'utf8'));
const run = root?.data?.pipelineRuns?.[0] || null;
if (!run) {
  console.error('no pipelineRuns in status file');
  process.exit(4);
}

const VERSION_RE = /\b(\d+\.\d+\.\d+\.\d+)\b/g;
const DONE_STATUSES = new Set([14]);

function harvest(obj, out) {
  if (obj == null) return;
  if (typeof obj === 'string') {
    let m;
    while ((m = VERSION_RE.exec(obj)) !== null) out.push(m[1]);
    return;
  }
  if (typeof obj === 'object') {
    for (const value of Array.isArray(obj) ? obj : Object.values(obj)) {
      harvest(value, out);
    }
  }
}

function pickLatest(arr) {
  if (!arr.length) return null;
  return [...arr].sort((a, b) => {
    const pa = a.split('.').map(Number);
    const pb = b.split('.').map(Number);
    for (let i = 0; i < 4; i += 1) {
      if (pa[i] !== pb[i]) return pa[i] - pb[i];
    }
    return 0;
  })[arr.length - 1];
}

function isTtpJob(job) {
  const text = JSON.stringify({
    jobName: job.jobName,
    jobId: job.jobId,
    uniqueId: job.jobAtom?.uniqueId,
    inputs: job.jobAtom?.inputs,
    rawInputs: job.jobAtom?.rawInputs,
  });
  return /ICM镜像构建TTP|icm_build_atomic_ttp_from_cn/i.test(text) || /US-TTP/i.test(text);
}

function extractVersion(job) {
  const output = job.jobAtom?.output || {};
  const candidates = [];

  if (typeof output.image_version === 'string') candidates.push(output.image_version);
  for (const item of output.build_status_list || []) {
    if (typeof item?.image_version === 'string') candidates.push(item.image_version);
  }
  harvest(output, candidates);

  return pickLatest([...new Set(candidates)]);
}

const ttpJobs = (run.jobs || []).filter(isTtpJob);
if (!ttpJobs.length) {
  console.error('no TTP image build job found in bits status file');
  process.exit(5);
}

const version = pickLatest(
  ttpJobs.map(extractVersion).filter(Boolean),
);

if (version) {
  process.stdout.write(version);
  process.exit(0);
}

const pending = ttpJobs.find((job) => !DONE_STATUSES.has(job.jobStatus));
if (pending) {
  console.error(`TTP image build not finished yet (jobStatus=${pending.jobStatus})`);
  process.exit(6);
}

console.error('no TTP image version (X.X.X.X) found in TTP job output');
process.exit(5);
NODE

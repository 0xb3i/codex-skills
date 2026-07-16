---
name: "argos-tools"
description: "Run Argos tools with automatic output saving. Invoke when needing to fetch logs, query log services, or use any `log.*` tool."
---

# Argos Tools

This command provides a dedicated interface for running Argos tools with enhanced capabilities for handling large outputs.

## Usage

```bash
argos tool log <subcommand> [json_input] [options]
```

### Subcommands

The `<subcommand>` corresponds to the suffix of any `log.*` tool. For example:
- `argos tool log search.keywords` runs `log.search.keywords` (Keyword Search — recommended)
- `argos tool log error_log` runs `log.error_log` (Error Log Overview)
- `argos tool log local_file` runs `log.local_file` (Local File Search)
- `argos tool log logid_prune` runs `log.logid_prune` (LogID Trace)
- `argos tool log key_word_v2` runs `log.key_word_v2` (legacy keyword search, prefer `search.keywords`)

> **Tip:** Always run `argos tool log <subcommand> -h` first to check the latest input schema and required parameters (e.g., `start`, `end`, `region`).

Run `argos tool log` (without subcommand) to see all available subcommands.

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `-e, --env <env>` | Target Argos runner environment, one of `dev` / `boe` / `cn` / `i18n` / `i18n-bd` / `sandbox` | `cn` (or whatever `argos config` sets) |
| `--project <name>` | Project name (binds the JWT to a specific project). **Required** when running with a service-account JWT. | From config / default |
| `--json` | Output result in JSON format | `false` |
| `--limit <n>` | Stdout output length threshold; longer outputs print only the saved file path | `10240` (10KB) |
| `--timeout <seconds>` | Per-call timeout | `300` |
| `-h, --help` | Show help for a specific subcommand | - |

### JSON Input

You pass tool-specific arguments as a single JSON string. This ensures complex nested structures (like arrays or objects) are handled correctly without ambiguity.

You can provide the JSON input in two ways:
1. As a command-line argument.
2. Via Standard Input (stdin) - **Recommended for complex JSON or automated tools** to avoid shell escaping issues.

**Examples:**

```bash
# search.keywords — keyword search (recommended, start/end in RFC3339)
echo '{"psm": "apm.argos.ai_agent_center", "region": "China-North", "keywords": ["error", "timeout"], "start": "2026-05-12T03:00:00Z", "end": "2026-05-12T03:30:00Z"}' | argos tool log search.keywords

# search.keywords — without keywords (fetch all logs for the PSM)
echo '{"psm": "apm.argos.ai_agent_center", "region": "China-North", "start": "2026-05-12T03:00:00Z", "end": "2026-05-12T03:30:00Z"}' | argos tool log search.keywords

# logid_prune — trace a LogID (no time range needed)
echo '{"log_id": "02177855432476300000000000000000000ffff0ace751160db39", "region": "China-North"}' | argos tool log logid_prune

# error_log — error overview (start/end in Unix seconds, aggregator required)
echo '{"psm": "apm.argos.ai_agent_center", "region": "China-North", "start": 1778556000, "end": 1778557800, "aggregator": "location"}' | argos tool log error_log

# local_file — search logs on specific pods (env + pod_names + seek_position required in prod)
echo '{"psms": ["apm.argos.ai_agent_center"], "regions": ["China-North"], "env": "prod", "pod_names": ["dp-b4c4202c59-6cf9c59765-98zth"], "limit": 50, "seek_position": {"time_range": {"start_time": "2026-05-12T03:00:00Z", "end_time": "2026-05-12T03:30:00Z"}}}' | argos tool log local_file
```

### Default Parameters

When the user does not specify certain parameters, apply the following defaults:

| Parameter | Default Behavior |
|-----------|-----------------|
| `region` | Use `"China-North"`. If the query returns empty, retry with `"China-East"`. **Exception**: for `logid_prune` the CLI auto-injects `region: "auto"` when omitted, but for **v1 LogIDs** you must still ask the user explicitly (see logid_prune hints) — `auto` cannot disambiguate them. |
| `start` / `end` | Default to the **last 30 minutes** (compute dynamically using current UTC time in RFC3339 format). |
| `keywords` | If user provides no keywords, omit this field to fetch all logs for the PSM. |

### logid_prune Parameter Hints

- Only requires `log_id` and `region`. No time range parameters (`start`/`end`/`scan_span_in_min`) needed — the backend auto-locates the time window.
- Optionally pass `psm_list` to filter results to specific services. `psm_list` should be standard PSMs.
- Results can be very large (10MB+) for busy request chains. Always read only the first 50–80 lines to summarize for the user.

#### LogID Formats

| Version | Pattern | Example |
|---------|---------|---------|
| v1 | 14-digit timestamp + random suffix | `20170111104055010006131078058EAC` |
| v2 | `02` prefix + 13-digit millisecond timestamp + random suffix | `021742526761243fdbddc0100180041234054b2cb00000360e83e` |

- **v1 LogIDs require an explicit `region` — never default.** The CLI will auto-inject `region: "auto"` when you omit it, but `auto` cannot infer the region for v1 LogIDs and the backend will fail or return empty. If the user did not specify a region for a v1 LogID, **stop and ask** before querying (offer the typical options: `China-North` / `China-East` / others the user knows). v2 LogIDs work fine with `auto` or an explicit region.
- When the user provides multiple LogIDs, query them serially (max 2 in parallel) and dedupe identical `log_id`+`region` pairs to avoid redundant downloads.

### search.keywords Parameter Hints

- `psm` is a **single string** (e.g., `"apm.argos.ai_agent_center"`), not an array.
- `keywords` is a simple **string array** (e.g., `["error", "timeout"]`). Multiple keywords are matched with AND logic.
- `start`/`end` use **RFC3339 format** (e.g., `"2026-05-12T03:00:00Z"`).
- `level`: filter by log level (e.g., `["Warning", "Error"]`).
- `error_log_preferred`: when `true`, first queries Warning+ logs; if empty, falls back to all levels.
- `with_logid_link`: when `true`, includes clickable LogID links in results.
- `limit_log_count`: limits the number of returned logs (default 100).
- `deduplication`: when `true`, deduplicates similar log lines.

### key_word_v2 (Legacy)

Legacy tool — prefer `search.keywords` for new queries. The CLI auto-converts a `"keywords"` array to `keyword_filter_include` for backwards compatibility.

### error_log Parameter Hints

- **Required fields**: `psm` (string, not array), `region`, `start`, `end`, `aggregator`.
- `start`/`end` use **Unix timestamps in seconds** (integer), NOT RFC3339 — different from `search.keywords`.
- `aggregator` is **required** — pass `"location"` unless you have a specific reason to aggregate differently. Without it the backend returns `unsupported aggregator` error.
- `psm` is a single string (e.g., `"apm.argos.ai_agent_center"`), not an array.
- Returns structured JSON with error counts grouped by code location, including Kibana links and metrics links.

### local_file Parameter Hints

- **Required fields**: `psms`, `regions`, `env`, `seek_position`.
- `seek_position` is **required** — without it the backend returns `seek position is nil`. Use `time_range` mode with `start_time`/`end_time` in RFC3339 format.
- `env` is **required** — use `"prod"` for production. Without it returns `unknown env` error. Note: this `env` is a **payload field** consumed by the backend, distinct from the CLI's `-e/--env` flag (which selects the Argos runner environment); pass it inside the JSON, not as a CLI flag.
- In production (`env: "prod"`), `pod_names` is **mandatory** — the backend refuses queries without specific pods (`pods len should not be empty`). Ask the user for pod names or retrieve them from prior log results.
- `psms` and `regions` are arrays (plural form), unlike other tools.
- Useful for searching specific log files (e.g., custom paths) or when you need line-level context (`context_mode`).

### Retry Policy

1. **No automatic retry**: Do not silently re-run a failed log query in the background.
2. **Confirm before retry**: On first failure, clearly show the failure reason and ask the user whether to retry; only proceed after confirmation.
3. **Max retries**: Default max 1 retry; if the user requests more, cap at 3, and confirm each time.
4. **Do not retry on parameter errors**: If the error is due to missing required params or format errors, prompt the user to fix them instead of retrying.

### Query Strategy

1. **LogID queries first**: When the user provides a LogID (even with a PSM), prefer `logid_prune` with just `log_id` and `region`. No time range needed.
2. **Error overview**: When the user asks about errors/exceptions/panics for a service (without a specific keyword), prefer `error_log` — it gives aggregated error counts by location.
3. **Keyword search**: When the user provides specific keywords or wants raw log lines, use `search.keywords`.
4. **Local file search**: When the user needs logs from a specific pod or specific log file path, use `local_file`. Requires pod names in production.
5. **No concurrent queries (with one exception)**: Multiple queries must run serially — wait for the previous one to complete. The only exception is `logid_prune`: when tracing multiple distinct LogIDs, you may run **up to 2 in parallel**, and must dedupe identical `log_id`+`region` pairs.
6. **Split large time ranges**: Queries spanning >3h should be split into ≤3h serial requests to reduce timeouts and backend pressure.
7. **Narrow before expanding**: Prefer adding keyword filters to narrow results before expanding time ranges.

### Presenting Results to the User

Every call writes its full output to `~/.sre-agent/tool-logs/<tool>-<timestamp>.log` regardless of size, and prints a `(task: <task_id>)` line at the end (when the backend returns one). Surface the `task_id` to the user on both success and failure — it's the canonical handle for follow-up tracing on the Argos platform.

When the output exceeds the `--limit` threshold, stdout shows only the file path:
1. **Read the first 50–80 lines** of the saved file to get a representative sample.
2. **Summarize** the log patterns observed: log levels (Info/Warn/Error), main activities, key endpoints, error messages.
3. **Report the file path and `task_id`** so the user can inspect the full output / file a ticket.
4. **Ask follow-up**: Offer to filter by keyword, log level, or time range if the user needs more specific results.

When the output is inline (within limit):
- Present it directly, highlighting any errors or warnings, and still surface the `task_id` line.

## Features

1. **Automatic Output Saving**:
   - **Every call** writes its full output to `~/.sre-agent/tool-logs/<tool>-<timestamp>.log`, regardless of size.
   - When the output exceeds `--limit` (default 10KB), stdout prints only the file path; otherwise the output is shown inline AND the file is still saved.
   - You can adjust the inline threshold with `--limit`.

2. **Direct JSON Input**:
   - Simplifies argument passing by using standard JSON format.
   - Eliminates ambiguity in parsing arrays, numbers, and booleans.
   - Supports complex nested objects easily.

3. **Error Handling**:
   - Provides clear error messages for invalid environments or tool failures.
   - **JSON Output**: When using `--json`, two error shapes may appear and agents should handle both:
     - Tool-level failure (the call completed but the tool reports an error): `{ "content": [...], "isError": true, "taskId": "..." }`
     - Transport / command failure (connection drop, timeout, non-zero exit): `{ "isError": true, "error": "...", "taskId": "..." }`
   - On any failure the CLI also prints `(task: <task_id>)` to stderr when available — preserve it in user-facing reports.
   - Validates JSON format before execution.
   - Exit code 1 on failure.

## Installation

Install the CLI (one-time):

| Environment | Command |
|---|---|
| CN (Linux/macOS) | `sh -c "$(curl -L https://argos.byted.org/cli/install.sh)" && export PATH=~/.local/bin:$PATH` |
| devbox (Linux/macOS) | `sh -c "$(curl -L https://sre-agent-cli.gf-boe.bytedance.net/cli/install-boe.sh)" && export PATH=~/.local/bin:$PATH` |
| npm (Linux/macOS) | `npm install -g @byted/argos@latest --registry https://bnpm.byted.org` |

Manual fallback (via bitscli plugin):

```bash
npm install -g @byted/bits-cli@latest --registry https://bnpm.byted.org
bitscli plugin install argos
```

Upgrade with `argos update`. See the `argos` skill for the full preflight / auth flow.

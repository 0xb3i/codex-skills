---
name: argos
description: Argos Agent Skill 通过 CLI 诊断服务问题、分析报警、追踪请求、查看服务可用性/延迟/错误率、分析日志/Panic 及读取配置。该技能在用户询问 SRE 相关问题、服务监控、报警分析或基础设施调试时被触发。
---

# Argos SRE Agent Skill

**允许的工具**: `Bash`

## 执行流程

当用户提出 SRE 相关问题时，按以下顺序执行：

1. **预检查**（每个会话仅一次） → 确认 CLI 已安装并可执行
2. **构造命令** → 根据用户意图选择 `argos run` 或 `argos tool log`
3. **执行命令** → 运行并获取输出
4. **解析输出** → 检测认证错误，提取关键信息
5. **向用户报告** → 总结发现，展示 session ID

---

## 一、前置依赖

### 1.1 安装 CLI

**自动安装**（预检查脚本会自动执行，见 1.2）：

| 环境 | 安装命令 |
|---|---|
| CN (Linux/macOS) | `sh -c "$(curl -L https://argos.byted.org/cli/install.sh)" && export PATH=~/.local/bin:$PATH` |
| devbox (Linux/macOS) | `sh -c "$(curl -L https://sre-agent-cli.gf-boe.bytedance.net/cli/install-boe.sh)" && export PATH=~/.local/bin:$PATH` |
| npm (Linux/macOS) | `npm install -g @byted/argos@latest --registry https://bnpm.byted.org` |

**手动安装**（自动安装失败时引导用户在普通终端执行）：

```bash
npm install -g @byted/bits-cli@latest --registry https://bnpm.byted.org
bitscli plugin install argos
```

安装后二进制位于 `~/.local/bin/argos`（Linux/macOS）或 `%USERPROFILE%\.local\bin\argos.exe`（Windows）。

**升级 CLI**：`argos update`

### 1.2 预检查（会话首次查询前执行一次）

```bash
ARGOS_BIN="$(command -v argos 2>/dev/null || true)"
if [ -z "$ARGOS_BIN" ] && [ -x "$HOME/.local/bin/argos" ]; then
  ARGOS_BIN="$HOME/.local/bin/argos"
fi
if [ -z "$ARGOS_BIN" ]; then
  echo "NOT_INSTALLED"
else
  echo "INSTALLED: $ARGOS_BIN"
fi
```

**处理预检查结果：**

| 输出 | 动作 |
|---|---|
| `INSTALLED` | 直接执行查询 |
| `NOT_INSTALLED` | 引导用户按 1.1 安装 CLI，安装后运行 `argos` 扫码登录；不要自动执行 `curl \| sh` 安装命令 |

### 1.3 认证

**首次登录**：在普通终端（非 IDE 沙盒）执行 `argos`，飞书扫码完成认证。

**i18n/BOE 用户**：先切换环境 `argos config set env i18n`

**JWT 登录**（CI/CD 或无法扫码场景）：

```bash
export ARGOS_JWT_TOKEN="<token>"
```

> JWT 为敏感信息，不要直接回显给用户。

**认证错误检测**：执行查询后，若输出包含以下任一关键词，说明需重新认证：

`unauthorized` | `auth failed` | `login required` | `扫码` | `认证失败` | `token.*expired` | `过期`

检测到后告知用户：
- 方式 1：普通终端运行 `argos` 扫码
- 方式 2：`export npm_config_registry=https://bnpm.byted.org/ && npx -y skills get-jwt` 获取 JWT 后 `export ARGOS_JWT_TOKEN="<token>"`

### 1.4 沙盒 / Trae Solo 环境适配

在 Trae Solo 或沙盒环境中：

| 问题 | 处理方式 |
|---|---|
| PATH 不完整 | 始终使用绝对路径 `~/.local/bin/argos` |
| SSL 证书验证失败 | 命令前添加 `NODE_TLS_REJECT_UNAUTHORIZED=0` |
| 子 shell 问题 | 不要包装在子 shell 中，直接调用二进制 |

---

## 二、命令模板

### 2.1 通用查询（argos run）

```bash
$ARGOS_BIN run "<用户问题，使用中文>" --output-format text -y --timeout 300000 --show-session
```

| 标志 | 说明 |
|---|---|
| `-y` | 必选，自动确认工具执行 |
| `--timeout 300000` | 必选，默认 5 分钟；超长查询用 `600000`（10 分钟） |
| `--show-session` | 必选，输出 session ID 供用户后续引用 |

### 2.2 日志查询（argos tool log）

```bash
$ARGOS_BIN tool log <subcommand> '<json_input>'
```

| 子命令 | 用途 |
|---|---|
| `logid_prune` | LogID / TraceID 追踪 |
| `key_word_v2` | 关键词搜索日志 |
| `error_log` | 错误日志概览 |
| `local_file` | 本地文件搜索 |

> 运行 `argos tool log <subcommand> -h` 获取最新参数 schema。

---

## 三、命令选择决策

| 用户意图 | 使用命令 |
|---|---|
| 分析报警链接 / group_id | `argos run "分析这个报警: <链接>"` |
| 追踪 logid / traceid | `argos tool log logid_prune '{"log_id":"<id>","scan_span_in_min":1}'` |
| 服务可用性 / 延迟 / 错误率 | `argos run "查看 psm=<psm> 最近<时间>的可用性和延迟"` |
| 错误日志分析 | `argos run "分析 <psm> 的错误日志"` |
| 关键词搜索日志 | `argos tool log key_word_v2 '{"psm_list":["<psm>"],"region":"<region>","limit":200}'` |
| 读取配置 | `argos run "帮我读配置 <路径或描述>"` |
| 分析历史 session | `argos run "分析 session <session_id> 的执行过程"` |

**优先级**：当用户同时给出 LogID 和 PSM 时，优先使用 `argos tool log logid_prune`。

---

## 四、强制规则

### 命令执行

- 始终使用 `run` 子命令，禁止使用 `chat`（AI 无法进行交互式终端会话）
- 始终带 `-y` 标志自动确认
- 除非用户明确指定环境，不要设置 `-e` 参数
- 传递给 `run` 的问题使用中文（SRE Agent 针对中文查询优化）
- 用户未提供具体问题时，先询问再执行
- 始终向用户展示 `--show-session` 输出的 session ID

### 日志查询策略

- `logid_prune`：`scan_span_in_min` 默认传 `1`，避免大范围扫描
- `key_word_v2`：`limit` 首次传 `200`；返回满 200 条时可扩至 `1000`；仍不够则建议用户精确关键词
- 时间范围 >3h 时，拆分为多个 ≤3h 的请求串行执行
- 多次查询必须串行执行，禁止并发
- 优先通过精确关键词收窄结果，再考虑扩大时间范围

### 重试策略

- 执行失败后不自动重试，向用户展示失败原因并询问是否重试
- 用户确认后最多重试 3 次，每次均需确认
- 参数校验失败（缺少必填参数、格式错误）不进入重试流程，提示用户修正参数

### Shell 安全

- 禁止使用 `set -u` 或 `set -euo pipefail`（zsh 中会导致 `RPROMPT: parameter not set` 错误），如需严格模式使用 `set -eo pipefail`
- 禁止读取 `~/.sre-agent/sessions/` 文件，session 分析通过 `argos run` 命令本身处理

---

## 五、参数参考

### run 子命令参数

| 参数 | 描述 | 默认值 |
|---|---|---|
| `-e, --env <env>` | 环境（cn / i18n / boe / sandbox） | `cn` |
| `-a, --agent <name>` | Agent 名称 | `Common` |
| `-m, --model <model>` | 模型覆盖 | - |
| `-y, --yes` | 自动确认工具执行 | `false` |
| `-o, --output-format <format>` | 输出格式（text / json / stream-json） | `text` |
| `--max-turns <n>` | 最大 Agent 轮次 | - |
| `--timeout <ms>` | 超时时间（毫秒） | - |
| `--session <id>` | 恢复已有 session | - |
| `--show-session` | 执行后打印 session ID | `false` |
| `--verbose` | 显示思考过程和工具调用详情 | `false` |

### 帮助命令

| 命令 | 用途 |
|---|---|
| `argos -h` | 查看所有顶层命令 |
| `argos run -h` | 查看 run 子命令参数 |
| `argos tool log <subcommand> -h` | 查看日志工具参数 schema |

> 用户文档：<https://bytedance.larkoffice.com/docx/Ov8LdUalKowm63xWNxyckgkUn1e>

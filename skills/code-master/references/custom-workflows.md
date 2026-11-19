# 自定义工作流检测

本文档定义「自定义工作流检测」主线的执行方式。这条主线与通用检测工作流（`general-workflow.md`）**并行**运行，针对**同一 diff 范围**执行仓库专属的检测规约。

## 目录

- 输入：custom_workflows.json
- preflight 产物与约束
- 如何执行单个 workflow（含 0.5 codespec 类型判定）
- 韧性
- codespec 类型工作流

## 输入：custom_workflows.json

本主线由 review-mode.md Step 1 集成 preflight 拉取得到的 `$WORK_DIR/custom_workflows.json` 驱动，结构如下：

```json
{
  "repo": "devinfra/bits-cli",
  "workflows": [
    {"id": "dev-infra", "name": "code-compliance-checker", "content": "执行 code-compliance-checker skill 检测"}
  ]
}
```

`workflows` 非空时，对每个**未标记 `"status": "skipped"`** 的 workflow 委派一个独立的并行 task agent（与通用分组评审的 task agent 同批并行）执行检测。每个 workflow 的 `content` 是一条**自然语言检测指令**。

> **派发即资源就绪**：若 preflight 判定某条 workflow 的检测资源不可用（如 codespec 规则拉取为空），会在该条目上回写 `"status": "skipped"` 与 `"skip_reason"`。派发时直接跳过这些条目（日志记一行原因即可），保证每个进场的 subagent 手里的资源必然完整。

> 拉取脚本同时为每条 workflow 在 `$WORK_DIR/custom/` 下落了一个**自包含规则文件** `workflow_<idx>.md`（`<idx>` 为该 workflow 在 `workflows` 数组中的下标，从 0 起），其中逐字嵌入了该条的 `content` 原文与执行协议。委派 subagent 时只传这个文件路径即可，规则原文由 subagent 自行打开读取，无需在派发指令里转述。

## preflight 产物与约束

review-mode.md Step 1 的 `diff_and_filter.py` 会在 diff 过滤完成后立即执行统一 preflight：

```bash
python3 "$SKILL_ROOT/scripts/diff_and_filter.py" \
  --diff-range "<range>" \
  --repo-root "$REPO_ROOT" \
  --output-dir "$WORK_DIR"
```

该脚本会在内部调用 `codespec_preflight.py`，完成自定义 workflow 拉取与明细打印；当存在 codespec 类型 workflow 时，继续完成 codespec workflow 校验、codespec 资源目录初始化、本地检测指令渲染和摘要打印。执行后日志中必须能看到自定义 workflow 摘要：

```text
[custom-workflows] workflow_count=<N>
[custom-workflows] workflow idx=<idx> type=<CUSTOM|CODESPEC> id=<id> name=<name> file=<WORK_DIR>/custom/workflow_<idx>.md
```

`workflow_count=0` 表示仓库未配置自定义工作流，后续跳过本主线，只执行通用检测主线。若未发现 codespec 类型 workflow，日志会打印跳过 codespec 资源目录初始化，此时不会生成 `codespec_pe.md`，也不视为失败。

若命中 codespec 类型 workflow，日志还必须能看到：

```text
[codespec] preflight summary: repo=..., rule_count=..., pe_source=..., debug_dir=..., error=...
```

**可选资源失败不阻塞**：preflight 中自定义 workflow 与 codespec 规则都是可选资源，拉取失败或为空不会让脚本非 0 退出——diff 过滤成功脚本即返回 0。如果 `query_spec_skills` 因 DNS/网络失败或仓库未配置导致 `rule_count=0`，或检测指令渲染失败，preflight 会把该条 codespec workflow 回写标记 `"status": "skipped"`（附 `skip_reason`），派发侧跳过该条目，避免 subagent 空跑消耗 token；其他 workflow 与通用检测主线不受影响。

日志控制：不要把渲染后的完整 `codespec_pe.md`、`spec_rule.md` 等大文件完整回显到 stdout；需要排查时直接读取 `$WORK_DIR/codespec/` 下的落盘正本。

preflight 只表示检测资源准备完成，不表示已经完成评审。日志中出现 `workflow_count`、`rule_count`、`codespec_pe.md` 只能说明 workflow / 规则 / 检测指令已就绪；后续仍必须执行通用检测和自定义 workflow 检测，并在 Step 5 写出 `$WORK_DIR/final_comments.json`。

评审完成的判据是 Step 5 写出的 `$WORK_DIR/final_comments.json`（合法 JSON 数组，0 缺陷为 `[]`），并由 `validate_final_comments.py` 在发布评论/对话交付前校验；文件缺失或非数组都视为评审未完成。

## 如何执行单个 workflow

委派的 task agent 按以下步骤执行：

### 0. 先逐字读取规则文件

打开并**逐字读取** `$WORK_DIR/custom/workflow_<idx>.md`，以该文件「检测指令」一节中的 `content` 原文为准。**不要采用派发指令里转述/概括的规则文本**——规则可能很长，转述容易截断或意译，只有文件里的原文是完整权威的版本。

### 0.5 判断是否为 codespec 类型工作流

读取规则文件后，先判断本条 workflow 是否为 **codespec 类型**：

- **判定方法**：该 workflow 的 `name` 或 `content`（即 `workflow_<idx>.md` 的「检测指令」原文）中，命中关键字 `codespec` / `code_spec` / `devspec`（大小写不敏感）。
- **命中 codespec 类型** → 跳转到本文档末尾「codespec 类型工作流」小节执行（先确认资源目录与检测指令产物，再按 `references/codespec-workflow.md` 检测），**不再走下方第 1–3 步的通用自然语言检测流程**。
- **未命中** → 继续下方第 1–3 步，按普通自定义工作流执行。

> codespec 类型工作流仍属于自定义工作流检测主线，缺陷写入同一个 `custom/custom_<序号>.jsonl`，只是 `category` 标 `CODESPEC`、并多一步资源目录/检测指令准备。

### 1. 把 content 当作自然语言检测指令

- **必须严格按 `content` 描述的步骤逐项执行，不能凭经验或通用直觉自行发挥、增删或概括。** 若 `content` 给出了明确的步骤/检查顺序，照此顺序执行；规则要求做什么就做什么，不替它"优化"流程。
- `content` 描述了本条自定义工作流要做什么，按它的语义在当前 diff 范围内做针对性检测。
- `content` 给出具体检查项（命名规范、禁用 API、日志规约、错误码约定等）时，逐项对照变更代码检查；只给宽泛意图时，结合仓库语言与变更内容检测最贴合的确定性问题，避免泛化臆测。
- `content` 中可能提及某个工具或流程的名字，仅作为对检测意图的描述来理解，按其语义尽力检测即可，不依赖任何外部工具真实存在。

### 2. 检测范围（以 workflow 要求为主）

- 读 `$WORK_DIR/review_files.md`，拿到待评审文件列表与默认 `scope`（`diff_only` / `full_file`）。
- **范围以 workflow 的 `content` 要求为准**：如果 `content` 本身要求对**整文件/更大范围**做检查（如「全文件合规扫描」「检查整个文件的命名规范」这类仓库级规约），就按 workflow 的要求做完整文件检测，并在缺陷里照实标注行号——这类缺陷在 Step 5.3 不受 diff 范围过滤（见下）。若 `content` 未提出范围要求，则沿用 `review_files.md` 的默认 `scope`。
- diff 方向语义与通用检测一致：只对 `+` 行及存续上下文报缺陷，仅存在于 `-` 行（已删除）的问题不报。

### 3. 输出缺陷

把本 workflow 检测到的缺陷写入 `$WORK_DIR/custom/custom_<序号>.jsonl`（`<序号>` 取该 workflow 在 `workflows` 数组中的下标，从 0 开始，保证文件名唯一、不会因 `id` 重复或含非法字符而互相覆盖），每行一个缺陷 JSON 对象，结构与 review-mode.md「缺陷数据结构」一致：

```json
{"title": "...", "file": "path/to/file.go", "start_line": 42, "end_line": 45, "severity": "P1", "category": "CUSTOM", "confidence": 8, "suggestion": "...", "rationale": "自定义工作流 code-compliance-checker：<为何判定为缺陷>"}
```

- **`category` 统一填 `CUSTOM`**，无需按既有 7 维分类，便于在报告中区分来源。
- **`rationale` 注明命中的工作流名**，前缀形如「自定义工作流 <name>：」。
- 分级与置信度复用 `references/review-rule.md` 的统一标准（缺陷类型分层、P0/P1/P2、置信度 < 5 且非 P0 丢弃、外部契约降信、定级自检）。
- 当该 workflow 按上文「检测范围」做的是整文件/超出 diff 行的检测时，给缺陷额外加一个 `"scope": "full_file"` 字段，让 Step 5.3 跳过 diff 范围过滤、不误杀这类合规缺陷。
- **检测完成后必须写出 `custom_<序号>.jsonl`，没有命中任何缺陷时也要写出空文件**（0 字节即可）。该文件的存在就是本条 workflow 执行完成的证明：文件缺失会被 Step 5 判定为该单元未执行完成，而不是"无缺陷"。

## 韧性

单个 workflow 检测失败（指令无法理解、执行报错等）只跳过该条，不影响其他 workflow，也不影响通用检测主线；失败跳过的条目不写 jsonl，由主流程在日志里记原因。

> 去重、排序、过滤与 Top5 召回由 `general-workflow.md` Step 5 统一处理：自定义工作流缺陷单独成池、独立召回 Top5，不与通用检测缺陷竞争名额。

---

## codespec 类型工作流

当第 0.5 步判定本条 workflow 为 codespec 类型（`name`/`content` 命中 `codespec` / `code_spec` / `devspec`）时，**不走上方通用自然语言检测流程**，改为执行 codespec 规约检测：

### 步骤 1：确认 codespec preflight 产物

正常情况下资源已在 review-mode.md Step 1 的集成 preflight 中准备完成——本条 workflow 能被派发到这里，说明它未被标记 `status: skipped`，即 `$WORK_DIR/codespec/` 下的 `codespec_meta.json`（`rule_count > 0`）、`spec_rule.md`、`skills/<name>/`、`codespec_pe.md` 均已就绪，直接复用即可。

仅当上述文件缺失（如手动排查、目录被清理）时才重跑 preflight 脚本：

```bash
python3 "$SKILL_ROOT/scripts/codespec_preflight.py" \
  --output-dir "$WORK_DIR" \
  --repo-root "$REPO_ROOT"
```

- 必须传 `--repo-root "$REPO_ROOT"`：脚本在该目录下执行 `git remote` 解析仓库标识，不传则回退到当前工作目录，cwd 不在目标仓库内时会解析失败（属调用方配置问题，应补齐参数重试）。
- 脚本写出 `codespec/codespec_meta.json`（含 `rule_count`），并在拉到规则时落 `spec_rule.md` 与 `skills/<name>/`。重跑后若 `rule_count == 0`（仓库未配置 codespec 规约 / 拉取失败），脚本会把本条 workflow 标记 `status: skipped`——此时按单条失败跳过，不要退回普通自定义 workflow 流程，也不要继续 codespec 检测。

### 步骤 2：确认本地检测指令

- 若 Step 1 的集成 preflight 已经生成 `$WORK_DIR/codespec/codespec_pe.md`，本步骤直接复用。
- 若该文件缺失或为空，重跑步骤 1 的 `codespec_preflight.py`——渲染由脚本内部完成（加载内置 Jinja2 模板、注入 `spec_rule.md` 规则摘要与 `comment_lang`，并在 `codespec_meta.json` 标记 `pe_source=local_template`）。

### 步骤 3：按 codespec 规约检测并输出缺陷

读取 `references/codespec-workflow.md` 并**严格按其流程执行**。检测指令与规则原文的读取顺序、检测范围、上报前校验、缺陷输出格式（`custom/custom_<序号>.jsonl`、`category=CODESPEC`、rationale 与规则链接格式、0 缺陷空文件语义）的**唯一规范都在该文档中**，本文件不做复述——两处副本必然漂移，以 codespec-workflow.md 为准。

> codespec 类型工作流的缺陷与同主线其他自定义工作流缺陷**同池汇总、共享自定义池的 Top5 名额**（见 `general-workflow.md` Step 5）。命中 codespec 类型但 `rule_count == 0` 或检测指令不可用时，该条目通常已被 preflight 标记 `status: skipped`、根本不会派发；若 subagent 在检测中途才发现资源缺失，按单条失败跳过，不影响其他 workflow 与通用检测主线。

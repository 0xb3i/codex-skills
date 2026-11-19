# Codespec 检测（自定义工作流的一种类型）

本文档定义 **codespec 类型工作流** 的检测执行方式。codespec 检测**不是独立主线**，而是**自定义工作流检测主线下的一种工作流类型**：当某条自定义工作流命中 codespec 类型时（判定见 `references/custom-workflows.md` 第 0.5 步：`name`/`content` 含 `codespec` / `code_spec` / `devspec`），由该 workflow 的 subagent 先确认资源目录与检测指令（Step 1 preflight 已准备好，直接复用），再按本文档基于团队配置的 **codespec 规约**（devspec / codespecs）检测代码变更缺陷。缺陷写入该条 workflow 的 `custom/custom_<序号>.jsonl`、与自定义工作流缺陷同池，`category` 标 `CODESPEC`。

## 输入：codespec 资源目录产物

本流程由 `references/custom-workflows.md`「codespec 类型工作流」小节的步骤 1–2 准备得到的 `$WORK_DIR/codespec/` 目录驱动：

| 文件 | 来源 | 说明 |
| ---- | ---- | ---- |
| `codespec_meta.json` | `codespec_preflight.py` | 元数据：`repo` / `rule_count` / `skills[]` / `spec_rule_path` / `pe_source` / `pe_path` / `pe_template` |
| `spec_rule.md` | `codespec_preflight.py` | codespec 规则清单，条目以分隔线分隔 |
| `skills/<name>/` | `codespec_preflight.py` | 各规则配套 skill 包（含规则原文；对候选/命中规则必须继续读取，不能停留在摘要层） |
| `codespec_pe.md` | `codespec_preflight.py` | 已渲染的检测指令：由脚本加载内置 Jinja2 模板注入 `code_spec_rules` / `comment_lang` 后生成；其中 `code_spec_rules` 是规则摘要/索引，不是完整规则原文 |
| `debug/` | `codespec_preflight.py` | 仅拉取/渲染失败时写入：`query_spec_skills` 原始响应与 `codespec_debug.log`，用于排查 |

**前置条件**：仅当自定义 workflow 的 `name`/`content` 命中 codespec 类型，且 `codespec_meta.json` 的 `rule_count > 0` 时执行本检测。`rule_count = 0`（仓库未配置 codespec 规约 / 拉取失败）的条目会被 preflight 标记 `status: skipped`、派发侧直接跳过，正常不会进入本文档流程；若检测中途才发现资源缺失，按「单条 workflow 失败只跳过该条」处理，不影响其他 workflow 与通用检测主线。未配置 codespec 类型 workflow 的仓库不会进入本文档流程。

preflight 的摘要日志格式、失败跳过标记（`status: skipped`）与日志控制要求，统一见 `references/custom-workflows.md`「preflight 产物与约束」。资源就绪不等于评审完成——日志中出现 `rule_count` 或 `codespec_pe.md` 后，仍必须继续执行本文档的规则原文读取、判定和缺陷输出步骤。

## spec_rule.md 格式

各规则条目以一行分隔线 `--------------------------------------------` 分隔，字段为前缀行：

```
skill_name: life_house_go
scenarios: Go 并发场景
description: 检测 goroutine 数据竞争
skill_path: /tmp/.../skills/life_house_go
--------------------------------------------
skill_name: ...
```

`skill_name` 对应 `skills/<skill_name>/` 下的规则原文目录。`spec_rule.md` 只承担规则索引/摘要作用，不足以单独完成判定。检测时必须先用 `description` / `scenarios` / `skill_path` 判断哪些规则可能适用；一旦某条规则进入候选集，必须继续读取对应 skill 目录下的规则原文取得完整判定标准。若目录内存在 `rules.md`，必须优先完整读取；若 `SKILL.md` 或规则描述再引用其他文件，也必须继续跟进到被引用的规则原文。

`skill_name` 是规则集合或目录定位用的**内部标识**，不是对外展示名。生成缺陷、报告或最终回复时，**不得**把 `skill_name` 直接写进 `rationale` 或问题描述；对外只允许使用命中的**具体规则名 / rule_id / rule_url 对应锚点名**。若 `rules.md` 同时提供集合名和具体规则条目，必须使用具体规则条目名称。

若命中的具体规则定义位于 `rules.md` 中，还必须从该规则条目里读取 `rule_url` 字段，输出缺陷时随缺陷带出（格式要求见下文「输出缺陷」节）。若规则条目同时存在可读规则名、`rule_id` 与 `rule_url`，对外文案优先使用可读规则名；没有可读规则名时退化为 `rule_id`，再退化为 `rule_url` 锚点名。

## 如何执行 codespec 检测

执行 codespec 检测的 workflow subagent 按以下步骤执行：

### 0. 先读取检测指令 与规则原文

- **逐字读取 `$WORK_DIR/codespec/codespec_pe.md`**，以它为本次 codespec 检测指令（已由本地模板渲染完成）。该检测指令由模板注入 `spec_rule.md` 生成的 `code_spec_rules` 变量后生成，定义了检测器的角色、流程、输出规范——**严格按其要求执行，不得凭通用直觉自行发挥**。但要注意：`code_spec_rules` 只是规则摘要/索引，不能替代 skill 目录里的完整规则原文。
- 读取 `$WORK_DIR/codespec/spec_rule.md` 解析全部规则，先建立候选规则集合。
- 对每条候选规则，**必须**继续读取 `$WORK_DIR/codespec/skills/<name>/` 下的规则原文完成判定；若存在 `rules.md`，必须完整读取 `rules.md`，并从最终命中的规则条目中提取 `rule_url`；若 `SKILL.md` 或规则描述再引用其他规则文件，也必须继续读取到被引用文件为止。**禁止仅凭 `spec_rule.md` / `codespec_pe.md` 中的摘要直接产出或否决缺陷。**

### 1. 把每条 codespec 规则当作独立检查项

- **每条规则至少经过两阶段：摘要筛选 -> 原文判定。** `spec_rule.md` 负责帮助你筛出候选，真正的利用/不利用判断必须基于 `skills/<name>/` 下的规则原文。

- **每条规则是一次独立检查。** 规则文件列了 N 条，就对范围内所有文件做 N 次独立检查。
- **字面解释规则**，不软化、不放宽、不收窄。
- 规则含 scope 过滤逻辑时，自行在 `review_files.md` 范围内应用过滤。

### 2. 检测范围（以规则要求为主）

- 读 `$WORK_DIR/review_files.md`，拿到待评审文件列表与默认 `scope`（`diff_only` / `full_file`）。
- **范围以 codespec 规则要求为准**：若规则要求整文件 / 更大范围检查（如"全文件命名规范扫描"这类仓库级规约），按规则做整文件检测，并在缺陷里照实标注行号——这类缺陷在 `general-workflow.md` Step 5.3 不受 diff 范围过滤（缺陷需带 `"scope": "full_file"`）。若规则未提范围要求，沿用 `review_files.md` 默认 scope。
- diff 方向语义与通用检测一致：只对 `+` 行及存续上下文报缺陷，仅存在于 `-` 行（已删除）的问题不报。

### 3. 上报前校验（重要）

- 重读违规附近代码，确认未被上下文化解（如检查在调用方、事务在更高层包裹）；已化解则不报告。
- **规则匹配校验**：若检出结果引用了来自 skill 的 `rule_url`，必须：
  1. **规则匹配性校验**：打开 `rule_url` 对应规则内容，确认缺陷确实违反该规则（纠正规则错配——实际违反规则 A 却错引规则 B 的情况）。
  2. **问题真实性校验**：结合规则描述确认代码确实存在该问题，而非过度解读。不匹配则修正 `rule_url` 或移除该条。
- **原文读取校验**：若缺陷来自某条具体 codespec 规则，提交前自检是否已经读取过该规则在 `skills/<name>/` 下的原文文件；如果没有，回到规则目录补读后再决定是否保留缺陷。
- **链接完整性校验**：若缺陷命中了 `rules.md` 中的具体规则条目，提交前必须确认已取到该条目的 `rule_url`（格式要求见「输出缺陷」节）；如果尚未定位到 `rule_url`，先回到规则原文补读，补齐后再输出缺陷。

### 4. 输出缺陷（写入 custom 池）

把检测到的缺陷写入**本条 codespec 工作流对应的** `$WORK_DIR/custom/custom_<序号>.jsonl`（`<序号>` 取该 workflow 在 `custom_workflows.json` 的 `workflows` 数组中的下标），与自定义工作流缺陷同池，每行一个缺陷 JSON 对象，结构与 review-mode.md「缺陷数据结构」一致：

```json
{"title": "...", "file": "path/to/file.go", "start_line": 42, "end_line": 45, "severity": "P1", "category": "CODESPEC", "confidence": 8, "suggestion": "...", "rationale": "codespec 规则 life-mall-ensure-slice-nil-check：<为何判定为缺陷>。规则链接:https://devspec.bytedance.net/codespecs/..."}
```

- **`category` 填 `CODESPEC`**（区别于普通自定义工作流的 `CUSTOM`），便于在报告中区分来源。
- **`rationale` 注明命中的具体 codespec 规则名 / rule_id**，前缀形如「codespec 规则 <rule_name_or_rule_id>：」，并在问题描述最后追加 `规则链接:<rule_url>`。`<rule_url>` 使用可访问的完整 `http://`/`https://` 链接；MR 评论中保留该证据链接。
- `skill_name` 等内部标识不得透出对外，规则见「spec_rule.md 格式」节。
- `rule_url` 必须来自命中的 `rules.md` 条目中的 `rule_url` 字段，不能手写、猜测或引用未命中的其他规则链接。
- 分级与置信度复用 `references/review-rule.md` 的统一标准（缺陷类型分层、P0/P1/P2、置信度 < 5 且非 P0 丢弃、外部契约降信、定级自检）。codespec 规则自带分级/评分标准时优先按规则标准。
- 当按整文件 / 超 diff 行检测时，给缺陷额外加 `"scope": "full_file"`，让 Step 5.3 跳过 diff 范围过滤。
- `start_line` / `end_line` 为源文件整数行号（非 diff 行号）；`file` 为相对仓库根目录路径，禁止系统绝对路径。
- **检测完成后必须写出 `custom_<序号>.jsonl`，没有命中任何缺陷时也要写出空文件**（0 字节即可）。该文件的存在就是本条 workflow 执行完成的证明：文件缺失会被 Step 5 判定为该单元未执行完成，而不是"无缺陷"。

## 韧性

- 单条规则检测失败（规则无法理解、执行报错等）只跳过该条，不影响本条 workflow 内其他规则、其他 workflow 与通用检测主线。
- `codespec_pe.md` 缺失或为空、或 `rule_count == 0` 时，本条 codespec 工作流按「单条 workflow 失败只跳过该条」处理（见 `references/custom-workflows.md` 韧性）。
- 所有规则都无产出时，仍必须写出空的 `custom_<序号>.jsonl`（执行完成的产物证明，见「输出缺陷」节）。

> 去重、排序、过滤与 Top5 召回由 `general-workflow.md` Step 5 统一处理：codespec 缺陷与同主线其他自定义工作流缺陷**同池汇总、共享自定义池的 Top5 名额**，不与通用检测缺陷竞争名额。跨池去重时，若 codespec 缺陷与通用缺陷指向同一根因，保留 codespec 侧表达。

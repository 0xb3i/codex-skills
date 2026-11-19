# 审查模式（review）

用于 MR/PR、commit、分支、本地 diff 或明确指定的文件、模块与架构审查。仅审查时不修改源码；“审查并修复”先核实问题，再按实现模式修复并复查，发布时不得把已修复问题当作仍存在。

先读 [共享工程准则](shared-design.md)。只在用户目标内检查，以相关调用链作证据；仓库搜索范围可以超出 diff，报告范围仍受用户授权与变更归因限制。MR 评论交付沿用 [既有授权与去重规则](mr-comments.md)，讨论本技能不发送评论。

自然语言或 `$code-master` 均可触发：`CR <MR/PR 链接>`、`review <MR/PR/bits Change 链接>`、`review <commit1>..<commit2>`、`review <source> <base>`、`review <文件或模块>`；只说 review 时检查当前变更，无变更再检查最近一次 commit。显式 `CR` 的发布行为见 [MR 评论交付](mr-comments.md)，无需二次确认。

## 目录约定

执行流程开始前，先自行解析并记录以下 3 个必选目录，后续所有路径解析、文件定位和产物输出以这些目录为边界，避免目录识别错误导致定位偏差：

- `SKILL_ROOT`：`code-master` 根目录（`SKILL.md` 所在目录，不是本参考文件所在目录），用于定位 `scripts/`、`references/`、`assets/`
- `REPO_ROOT`：被评审项目的仓库根目录，所有 `git diff`、源码读取、`file` 字段路径基准都以此为准
- `WORK_DIR`：上下文指定的中间产物根目录，优先放当前工作区 `work/` 下；无工作区约定时用 `/tmp/<repo>_<session>/`。**确认路径后必须立即创建该目录**（`mkdir -p "$WORK_DIR"`）。

---

## Step 1：确定代码评审范围并过滤文件

根据用户意图确定 git diff 的范围，然后调用脚本一次性获取变更文件列表并过滤掉不需要评审的文件。

中间产物统一使用上文确定的 `WORK_DIR`，不要创建第二套工作目录。

### 范围判断规则

按优先级从高到低匹配：

| 场景                 | 用户信号                 | Diff 范围                                                                         |
| -------------------- | ------------------------ | --------------------------------------------------------------------------------- |
| 用户指定 MR/PR       | 给出 MR 链接 / MR ID / bits devops change 链接 / bits 客户端 MR 链接 | 按 `references/codebase-api.md`「get-mr-commits」节调用并直接使用其返回的 `diff_range` |
| 用户指定 commit 区间 | 给出两个 commit hash     | `<commit1>..<commit2>`                                                            |
| 用户指定分支（source+base） | 同时给出两个分支名                     | `<base>...<source>`（三点）                                                                          |
| 用户指定分支（仅 source）   | 只点名一个分支（如"review feat-x"）   | 必须先按下文「Base 分支确定流程」确定 base，再用 `<base>...<source>`；**禁止回退到 `HEAD~1..HEAD`** |
| 当前工作区有变更     | 默认                     | `HEAD`（含暂存和未暂存，不含未跟踪新文件）                                        |
| 当前工作区无变更     | 默认回退                 | `HEAD~1..HEAD`（最近一次 commit）                                                 |

### Base 分支确定流程（仅 source）

优先沿用用户或已有 MR 指定的 base；否则读取仓库约定与 `git symbolic-ref refs/remotes/origin/HEAD` 确定默认基准，说明采用的分支及来源后继续。存在多个合理基准且无法从上下文判断时，才询问用户；禁止静默回退到最近一次 commit。范围统一为 `<base>...<source>`，只包含共同祖先以来 source 的变更。

### 执行脚本

确定 diff 范围后，调用脚本同时输出 `diff_files.md`（原始变更列表）和 `review_files.md`（过滤后的待评审列表）：

```bash
python3 "$SKILL_ROOT/scripts/diff_and_filter.py" \
  --diff-range "<range>" \
  --repo-root "$REPO_ROOT" \
  --output-dir "$WORK_DIR"
```

**参数说明：**

| 参数 | 必填 | 说明 | 示例 |
| ---- | ---- | ---- | ---- |
| `--diff-range` | 是 | git diff 范围，直接透传给 `git diff` 命令。支持标准 git range 语法 | `HEAD~1..HEAD`、`commit1..commit2`、`base...source`、`HEAD` |
| `--repo-root` | 是 | 被评审仓库的根目录绝对路径，脚本在此目录下执行 git 命令 | `/path/to/repo` |
| `--output-dir` | 是 | 输出目录路径；脚本在此目录下写入 `diff_files.md`、`review_files.md`，并继续准备 `custom_workflows.json`（命中 codespec 类型 workflow 时还会生成 `codespec_pe.md`） | `$WORK_DIR` |

`--diff-range` 的值取决于上方范围判断规则的匹配结果：

- MR/PR → `<base_commit>...<source_commit>`（三点，从 Codebase API 获取的 commit）
- commit 区间 → `<commit1>..<commit2>`
- 分支对比 → `<base>...<source>`（三点，不要用二点）
- 工作区变更 → `HEAD`
- 最近一次提交 → `HEAD~1..HEAD`

脚本自动排除部分文件，stdout 输出过滤摘要。过滤只缩减默认主审列表，不限制契约取证：配置、依赖、协议、测试、动态注册与既有 API 即使被过滤，仍按共享准则补读；其中直接受本次变更影响的文本契约文件应补入待审列表。删除项检查对存续调用方的影响，不给不存在的新侧行号报缺陷。当前工作区的未跟踪源码用 `git ls-files --others --exclude-standard` 补查，不能因 `git diff HEAD` 不包含它们就漏审。

### 自定义工作流 preflight（同一次调用内完成）

部分仓库在服务端配置了**专属评审规约**。Step 1 是**强制准备步骤**：上述脚本在 diff 过滤之外，还在同一次调用里完成自定义 workflow 拉取，生成 `custom_workflows.json`；若服务端未返回任何 workflow，后续只执行通用检测主线。命中 codespec 类型 workflow 时，继续准备 `codespec/codespec_meta.json`、`codespec/spec_rule.md`、`codespec/skills/<name>/` 与 `codespec/codespec_pe.md`。

preflight 对可选资源**失败不阻塞**：workflow 拉取失败按未配置处理；codespec 规则拉取失败或为空（`rule_count=0`）、检测指令渲染失败时，对应 workflow 条目被回写标记 `"status": "skipped"` 与 `skip_reason`，脚本正常退出。Step 3 派发时跳过被标记的条目——**派发即资源就绪**，subagent 不会在进场后才发现资源为空。

Step 1 只做资源准备，**不代表已经完成评审**；后续仍必须进入 Step 3 执行通用检测与自定义 workflow 检测，并由通用工作流 Step 5 写出合法 JSON 数组 `$WORK_DIR/final_comments.json`。

preflight 的详细产物、日志要求、codespec 判定、规则原文读取、对外文案约束与失败跳过语义，统一见 `references/custom-workflows.md` 的「preflight 产物与约束」和「codespec 类型工作流」；具体 codespec 检测流程见 `references/codespec-workflow.md`。

### 异常处理（评审范围）

- 当前目录不在 git 仓库内：已知 MR 仓库时，自动在工作目录准备隔离 checkout 并固定审查 commit；不要要求用户先切目录。缺少仓库来源时才询问。
- 用户指定的分支/commit 不存在：提示确认名称，尝试 `git fetch origin` 后重试
- diff 结果为空或过滤后为 0：先检查用户是否指定整文件/模块审查及未跟踪源码；按 Step 2 补入实际目标后继续。确实无可审内容时说明范围和过滤限制，不把它当作已审查通过。
- 用户只给一个分支、又无法自动探测到 base 候选：不要自行选一个执行，必须停下来让用户指定 base 分支

---

## Step 2：用户指定范围筛选

如果用户指定了特定文件或函数，在 Step 1 的基础上进一步筛选。`review_files.md` 头部必须始终包含机器可读的 `scope` 字段。

### 指定文件列表

- 以用户指定的文件或模块范围为准，核实目标存在后补入 `review_files.md`；即使无 diff 或被默认过滤，也不能只取交集而漏掉目标。明确审查的是文件变更时才保留 `diff_only`。
- 将 `review_files.md` 头部的 `scope` 改为 `scope: full_file`
- 在 `review_files.md` 头部增加说明：`用户指定评审范围: file1.go, file2.go`

### 指定函数/代码片段

- 保留包含该函数的文件
- 将 `review_files.md` 头部的 `scope` 改为 `scope: full_file`
- 在 `review_files.md` 中标注关注的函数名：`重点关注: CreateOrder(), UpdateInventory()`
- 评审时优先检查标注的函数及其调用链

### 评审范围标记

当用户指定了文件或函数时，在 `review_files.md` 头部使用：

```markdown
scope: full_file
```

此标记表示评审范围以用户指定为准，最终缺陷不限于 diff 变更行内（后续工作流中的 diff 范围过滤会跳过）。

未指定时保持 Step 1 脚本默认生成的：

```markdown
scope: diff_only
```

如果用户未指定特定范围，跳过此步骤，不要删除默认的 `scope: diff_only`。

---

## Step 3：执行评审工作流

进入本步骤前，`$WORK_DIR/review_files.md` 与 `$WORK_DIR/custom_workflows.json` 应已由 Step 1 生成；若缺失，说明 Step 1 未成功完成，先重跑 `diff_and_filter.py` 再继续。

先按 [共享工程准则](shared-design.md) 调查仓库参照、可复用 API 与契约，并按 [架构与废弃路径审查](review.md) 检查相关边界，再按照 [通用检测工作流](general-workflow.md) 执行检测、定级和汇总。共享原则必须进入实际检测与缺陷过滤，不能只在开场声明。

本步骤包含两条检测主线。两条主线相互无依赖，存在多个独立检测单元时按可用并发槽位分批并行执行，不让一条主线阻塞另一条。单元数为 1 且无需上下文隔离时由主流程直接执行；无可用并发槽位时按通用工作流的 Fallback 执行，不遗漏单元。

派发的每个检测单元都必须读取 `code-master/SKILL.md`、`references/shared-design.md` 和本模式说明，获得准确的 `SKILL_ROOT`、`REPO_ROOT`、`WORK_DIR`、审查版本和范围；共享原则由通用主线完整覆盖，自定义单元据此核实契约但不扩大其规约范围。

1. **通用检测主线**（始终执行）：按 `references/general-workflow.md` 执行 7 维度 + 语言专项评审。小变更为 1 个检测单元，大变更按分组拆成 N 个单元。
2. **自定义工作流检测主线**（仅当 `custom_workflows.json` 的 `workflows` 非空时执行）：每条**未标记 `"status": "skipped"`** 的 workflow 为 1 个独立单元；被标记的条目资源不可用（原因见其 `skip_reason`），直接跳过、不派发。派发时只传该条的规则文件路径 `$WORK_DIR/custom/workflow_<idx>.md`（不要把 `content` 抄进 prompt），subagent 自行打开读取规则原文，并读取 `references/custom-workflows.md` 按其步骤执行。**若该条 workflow 命中 codespec 类型**（`name`/`content` 含 `codespec` / `code_spec` / `devspec`），subagent 按 `references/custom-workflows.md` 的「codespec 类型工作流」分支先确认资源目录与本地检测指令，再按 `references/codespec-workflow.md` 检测（含"必须下钻规则原文、不能只凭检测指令中的规则摘要判定"等全部执行要求）。

每个已派发的自定义 workflow（含 codespec 类型）完成检测后必须写出自己的 `$WORK_DIR/custom/custom_<序号>.jsonl`，**0 缺陷也要写出空文件**——文件存在性是该检测单元执行完成的唯一证明，缺失会被 Step 5 判定为单元未完成而非"无缺陷"。

**执行约束**：独立检测单元数量由通用检测分组数与服务端实际返回的 workflow 数共同决定。判定需要 subagent 时，立即发起实际 subagent/task agent 工具调用；若当前运行环境没有可用的 subagent/task agent 工具，按 `references/general-workflow.md` 的 Fallback 在主流程串行执行全部检测单元，并写出对应产物。

**最终产物要求**：外层 runner 以 `$WORK_DIR/final_comments.json` 是否为合法 JSON 数组作为评审完成的唯一判据——文件缺失或非数组都会被当作评审未完成，所以计划性文字不是产物，评审必须一直执行到通用工作流 Step 5 实际写出数组为止；0 缺陷也要显式写入空数组 `[]`。
各场景的派发策略详见 `references/general-workflow.md` Step 3 的决策表。

### 异常处理

- workflow 文件读取失败：终止流程，提示用户对应的引用文件缺失，输出缺失文件路径
- 评审过程中产出 0 个缺陷：在最终报告中明确告知"未发现缺陷"，不输出空报告
- diff 内容超大（变更行数 > 5000 行）：强制使用分组评审策略，并提示用户考虑缩小评审范围以提高检测质量

### 语言专项规则

评审时根据变更文件的语言类型加载对应的专项检测规则：

| 文件类型                                         | 专项规则文件 |
| ------------------------------------------------ | ------------ |
| `*.go`                                           | [references/lang-go.md](lang-go.md) |
| `*.ts` / `*.tsx` / `*.js` / `*.jsx` / `*.mjs` / `*.cjs` | [references/lang-typescript.md](lang-typescript.md) |
| 其他语言                                         | 无专项规则，仅使用通用评审维度（`references/review-dimensions.md`） |

> 目前 Go 与 TypeScript/JavaScript 有专项检测规则。其他语言使用通用维度进行检测，不加载额外规则文件。

---

## Step 4：交付与收尾

检测阶段仍须生成合法 JSON 数组 `$WORK_DIR/final_comments.json`（无缺陷为 `[]`），作为汇总和发布输入；它是临时数据，不是用户交付文件。先执行：

```bash
python3 "$SKILL_ROOT/scripts/validate_final_comments.py" "$WORK_DIR/final_comments.json"
```

校验不通过就修正产物，不以空数组冒充完成。通过后读取 [MR 评论交付](mr-comments.md)：

- MR/PR：按当前版本、现有线程和证据逐项去重，直接发布行级问题评论并回读确认。
- 本地文件/commit/分支：在对话中列出缺陷、位置、严重度、证据和建议；未指定 MR 时不自行寻找 MR 并发评论。
- 无缺陷：只在对话说明审查范围与验证限制，不创建“审查通过”占位评论。
- 默认不生成 HTML、Markdown 报告文件，不打开浏览器；用户明确要求导出时才另行制作其指定产物。
- 对话收尾简短报告问题数、实际新增/已存在/未发出数量、MR 链接及验证限制，不重复整份已发布评论。

完成校验和评论回读（或本地结论交付）后清理本次隔离 checkout、下载包和临时审查数据；不得删除用户仓库或用户文件。此时不再要求已消费的 `final_comments.json` 留在磁盘上。发布失败时先在对话完整保留未发出的缺陷和原因，再清理；不得声称已发布成功。

---

## 缺陷数据结构

每个缺陷用以下 JSON 结构表示：

```json
{
  "title": "共享 map 并发读写缺少同步保护",
  "file": "path/to/file.go",
  "start_line": 42,
  "end_line": 45,
  "severity": "P0",
  "category": "CONCURRENCY",
  "confidence": 9,
  "suggestion": "使用 sync.RWMutex 保护 map 的并发访问",
  "rationale": "共享 map 在多个 goroutine 中被并发读写，没有任何同步机制，会导致运行时 panic"
}
```

| 字段         | 类型   | 必填 | 说明                                                                                               |
| ------------ | ------ | ---- | -------------------------------------------------------------------------------------------------- |
| `title`      | string | 是   | 缺陷标题，一句话描述缺陷核心问题（非空）                                                           |
| `file`       | string | 是   | 相对于仓库根目录的文件路径                                                                         |
| `start_line` | number | 是   | 缺陷起始行号                                                                                       |
| `end_line`   | number | 是   | 缺陷结束行号                                                                                       |
| `severity`   | string | 是   | `P0` / `P1` / `P2`                                                                                 |
| `category`   | string | 是   | `LOGIC` / `BUSINESS_SEMANTICS` / `SECURITY` / `CONCURRENCY` / `ROBUSTNESS` / `PERFORMANCE` / `QUALITY` / `CUSTOM` / `CODESPEC` |
| `confidence` | number | 是   | 1-10 的置信度分数                                                                                  |
| `suggestion` | string | 否   | 修复建议，可包含代码片段                                                                           |
| `rationale`  | string | 是   | 为什么判定为缺陷的原因说明。`CODESPEC` 类缺陷对外只写命中的具体规则名 / rule_id，不得透出内部 `skill_name` / 规则集合名 |
| `scope`      | string | 否   | 自定义工作流 / codespec 按整文件检测时填 `full_file`，令该缺陷跳过 diff 范围过滤（见 `references/custom-workflows.md`、`references/codespec-workflow.md`） |

> `CUSTOM`：自定义工作流检测主线产出的缺陷统一使用此枚举（见 `references/custom-workflows.md`）。
> `CODESPEC`：codespec 类型自定义工作流产出的缺陷使用此枚举，与 `CUSTOM` 同池（见 `references/codespec-workflow.md`）。

---

## 参考文件说明

| 文件                                | 用途                                                                                               | 何时读取                      |
| ----------------------------------- | -------------------------------------------------------------------------------------------------- | ----------------------------- |
| [references/review-dimensions.md](review-dimensions.md)   | 评审维度：7 个维度定义及检测清单、误报规避规则                                                     | Step 3 执行评审时             |
| [references/review-rule.md](review-rule.md)         | 缺陷分级（P0/P1/P2）与置信度评分策略（1-10）                                                       | Step 3 执行评审时             |
| [references/general-workflow.md](general-workflow.md)    | 通用检测工作流：评审策略（直接/分组并行）、文件分组规则、缺陷汇总/去重/过滤/排序流程、评论与对话交付 | Step 3 执行评审时             |
| [references/custom-workflows.md](custom-workflows.md)    | 自定义工作流检测主线：把 workflow `content` 当自然语言指令执行、范围对齐、缺陷输出规则；含 codespec 类型工作流分支 | Step 3 执行自定义工作流检测时（`custom_workflows.json` 非空时） |
| [references/codespec-workflow.md](codespec-workflow.md)   | codespec 类型工作流子流程：初始化资源目录 → 基于 codespec 规约（`spec_rule.md` 摘要 + `skills/<name>/` 规则原文）检测、范围对齐、缺陷输出规则 | 自定义工作流命中 codespec 类型时 |
| `assets/codespec-pe-template.md.j2` | codespec 检测指令的本地 Jinja2 模板源文件：注入规则摘要后生成检测指令；不替代 `skills/<name>/` 下的完整规则原文 | 由 `codespec_preflight.py` 自动加载 |
| [references/lang-go.md](lang-go.md)             | Go 语言专项检测：变量遮蔽、nil map、channel 误用、类型断言、defer 陷阱等                           | 评审文件包含 `.go` 时         |
| [references/lang-typescript.md](lang-typescript.md)     | TypeScript/前端专项检测：业务响应语义、UI 状态切换、异步闭包 stale state、DTO 字段映射、前端鉴权与 token 注入 | 评审文件包含 `.ts` / `.tsx` / `.js` / `.jsx` / `.mjs` / `.cjs` 时 |
| [references/codebase-api.md](codebase-api.md)        | Codebase OpenAPI CLI 使用说明：仓库/分支/MR 查询、MR 行级评论创建                                  | 需要调用 Codebase API 时      |
| [references/mr-comments.md](mr-comments.md) | 默认发布授权、版本核对、评论去重、串行发布和回读 | MR 评论交付时 |
| [references/auth.md](auth.md)                | 凭据获取：CLOUD_JWT / CODEBASE_JWT 的获取方式                                                      | 需要获取认证凭据时            |
| `scripts/diff_and_filter.py`        | 执行 git diff 并过滤文件，并在同一次调用里完成自定义 workflow preflight；输出 `diff_files.md`、`review_files.md`、`custom_workflows.json`，命中 codespec 时继续准备 `codespec/` 产物 | Step 1 获取变更并完成准备时       |
| `scripts/fetch_custom_workflows.py` | 解析当前仓库标识并拉取仓库级自定义工作流，输出 `custom_workflows.json`                             | `diff_and_filter.py` 集成 preflight 内部调用，或手动排查时   |
| `scripts/codespec_preflight.py`     | preflight 编排入口：拉取自定义工作流、判定 codespec 类型、初始化 codespec 资源目录（`spec_rule.md` + skill 包 + `codespec_meta.json`）、渲染检测指令（`codespec_pe.md`），资源不可用时回写 `status: skipped` | `diff_and_filter.py` 集成调用；产物缺失需手动重跑时 |
| `scripts/validate_final_comments.py`| 校验 `final_comments.json` 必须存在且为合法 JSON 数组；缺失或结构错误时返回非 0，阻止误上报 success | Step 4 评论交付前 |
| `scripts/codebase.py`               | Codebase OpenAPI CLI：仓库/分支/MR 查询、从 MR/bits change URL 取 commit 范围、MR 行级评论创建     | 处理 MR/PR/bits change 场景（Step 1 取 base/source commit，或需要对 MR 留行级评论时） |

## 中间产物目录

所有中间文件保存在 `WORK_DIR` 下（见 Step 1 中的路径说明）：

| 文件                      | 产生步骤                | 说明                                      |
| ------------------------- | ----------------------- | ----------------------------------------- |
| `diff_files.md`           | Step 1                  | 原始 diff 文件列表                        |
| `custom_workflows.json`   | Step 1                  | 拉取到的仓库自定义工作流列表               |
| `custom/workflow_<idx>.md`| Step 1                  | 各自定义工作流的自包含规则文件（含 content 原文），供检测 subagent 逐字读取 |
| `codespec/codespec_meta.json` | codespec 类型工作流  | codespec 资源目录元数据（`rule_count` / `skills` / `pe_source` 等） |
| `codespec/spec_rule.md`   | codespec 类型工作流     | 拉取到的 codespec 规则清单                  |
| `codespec/skills/<name>/` | codespec 类型工作流     | 各 codespec 规则配套 skill 包（含规则原文；命中/候选规则必须继续读取） |
| `codespec/codespec_pe.md` | codespec 类型工作流     | codespec 检测指令（由本地模板渲染生成，仅包含规则摘要与执行要求，不替代规则原文） |
| `review_files.md`         | Step 1-2                | 过滤后的待评审文件列表（含 scope 元数据） |
| `review_groups.md`        | 通用工作流 Step 2       | 文件分组及依据（仅分组评审时）            |
| `group/group_<num>.jsonl` | 通用工作流 Step 3       | 各分组的缺陷列表（仅分组评审时）          |
| `custom/custom_<序号>.jsonl`| 自定义工作流 Step 3     | 各自定义工作流的缺陷列表（含 codespec 类型，`category=CODESPEC`）；0 缺陷时为空文件，作为该单元执行完成的证明 |
| `comments.jsonl`          | 通用工作流 Step 4       | 通用检测主线汇总的缺陷                     |
| `final_comments.json`     | 通用工作流              | 去重过滤后的最终缺陷列表                   |

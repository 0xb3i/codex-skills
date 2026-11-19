# 审查模式

用于 MR/PR、commit、分支、本地 diff，以及指定文件、模块和架构的审查。先读[共享工程准则](shared-design.md)，按用户目标核实代码与相关调用链。“审查并修复”先核实问题，再执行实现模式并复查；交付时说明修复后的实际状态。

`CR <PR 链接>`、`review <commit1>..<commit2>`、`review <source> <base>`、`review <文件或模块>` 均可触发。只说 review 时检查当前变更，无变更再检查最近一次 commit。评论发布见[MR 评论交付](mr-comments.md)。

## 目录与版本

开始前确定三个目录：

- `SKILL_ROOT`：`SKILL.md` 所在目录，用于定位脚本和参考文件。
- `REPO_ROOT`：被评审仓库根目录，作为 Git 命令和缺陷 `file` 路径的基准。
- `WORK_DIR`：本次临时数据目录，优先遵循工作区约定，否则使用系统临时目录中的独立子目录。确定后立即创建，所有审查数据集中于此。

通过[仓库访问](repository-access.md)读取远端目标。记录 base/head commit 与当前工作区状态；审查历史版本时从隔离 checkout 读取对应源码，不能拿最新工作区给旧版本标行号。

## 1 确定范围

| 场景 | Diff 范围 |
| --- | --- |
| 用户指定 MR/PR | 从平台读取 base/head commit，使用 `<base_sha>...<head_sha>` |
| 用户指定两个 commit | `<commit1>..<commit2>` |
| 用户指定 source 和 base | `<base>...<source>` |
| 用户只指定 source | 先确定 base，再用 `<base>...<source>` |
| 当前工作区有变更 | `HEAD`，另查未跟踪文件 |
| 当前工作区无变更 | `HEAD~1..HEAD`；首提交使用 Git 空树到 `HEAD` |

base 优先采用用户、现有 MR/PR 或仓库约定的值；否则读取默认远端分支，如 `git symbolic-ref refs/remotes/origin/HEAD`，说明采用的依据。多个基准都合理且无法判断时询问用户。指定分支不存在时先 fetch 后核实。

确定范围后执行：

```bash
python3 "$SKILL_ROOT/scripts/diff_and_filter.py" \
  --diff-range "<range>" \
  --repo-root "$REPO_ROOT" \
  --output-dir "$WORK_DIR"
```

三个参数均必填。脚本在目标仓库运行本地 Git 查询，输出：

- `diff_files.md`：原始变更文件与状态。
- `review_files.md`：过滤后的待审文件、增删行数和默认 `scope: diff_only`。
- `diff_stats.json`：范围、耗时、文件数、增删行数、语言分布和待审文件明细。

过滤只缩减默认主审列表。配置、依赖、协议、测试、动态注册与公共 API 仍按实际契约补读，直接受影响的文本契约文件补入待审列表。删除项检查存续调用方，不能报告已不存在的新侧行号。工作区审查另用 `git ls-files --others --exclude-standard` 检查未跟踪源码并补入列表。

当前目录不是目标仓库时，按已知来源准备隔离 checkout 并固定版本。Git 查询失败时先解决失败；列表为空时检查显式目标和未跟踪文件，确实无可审内容则说明范围，不能将其写成审查通过。

## 2 对齐显式目标

用户指定文件、函数或模块时，核实目标存在并补入 `review_files.md`，即使没有 diff 或被默认过滤也继续检查。文件头改为：

```markdown
scope: full_file
用户指定评审范围: src/example.go
重点关注: CreateOrder()
```

`full_file` 以用户指定范围的当前源码为准，缺陷不限于 diff 行；重点函数需检查相关调用链。用户明确只审查这些文件的变更时保留 `diff_only`。未指定目标时保持默认 scope。

## 3 执行审查

读取[架构与废弃路径审查](review.md)，再按[通用检测工作流](general-workflow.md)调查、分组、定级、汇总和过滤。每个检测者都读取本技能入口、共享准则和本流程，获得三个根目录、审查版本与范围。

始终检查[七个评审维度](review-dimensions.md)，根据文件类型补充语言专项：

| 文件类型 | 参考 |
| --- | --- |
| Go | [Go 专项](lang-go.md) |
| TypeScript / JavaScript，包括 TSX、JSX、MJS、CJS | [TypeScript / JavaScript 专项](lang-typescript.md) |
| 其他语言 | 通用评审维度和目标仓库规范 |

对适用的仓库规则读取原文，核实触发条件与当前代码。缺少关键规则或证据时说明检查限制；不能把读取失败当作规则不存在。

## 4 交付与清理

完成所有检测与汇总后，写出合法 JSON 数组 `$WORK_DIR/final_comments.json`，无缺陷时写 `[]`，并执行：

```bash
python3 "$SKILL_ROOT/scripts/validate_final_comments.py" "$WORK_DIR/final_comments.json"
```

校验失败先修正，不能用空数组代替未完成的审查。通过后按[MR 评论交付](mr-comments.md)发布已获授权的评论，或在对话中给出位置、严重度、证据和建议。无缺陷时说明范围与实际验证限制。

默认不另建报告文件。交付并回读评论后清理本次临时数据与隔离 checkout，保护用户仓库和用户文件。发布失败时先在对话保留未发出的缺陷与原因，再清理。

## 缺陷结构

```json
{
  "title": "共享 map 并发读写缺少同步保护",
  "file": "path/to/file.go",
  "start_line": 42,
  "end_line": 45,
  "severity": "P1",
  "category": "CONCURRENCY",
  "confidence": 9,
  "suggestion": "使用同步机制保护共享 map 的访问",
  "rationale": "多个 goroutine 会同时读写该 map，可能触发运行时 panic。"
}
```

| 字段 | 约束 |
| --- | --- |
| `title` | 非空，概括一个独立根因 |
| `file` | 相对仓库根目录的路径 |
| `start_line` / `end_line` | 当前审查版本中的有效新侧行号，最小定位区间 |
| `severity` | `P0` / `P1` / `P2`，按[定级规则](review-rule.md)确定 |
| `category` | `LOGIC` / `BUSINESS_SEMANTICS` / `SECURITY` / `CONCURRENCY` / `ROBUSTNESS` / `PERFORMANCE` / `QUALITY` |
| `confidence` | 1–10，按证据评分 |
| `rationale` | 必填，说明触发条件、契约与实际影响 |
| `suggestion` | 可选，指出准确的修复或复用入口 |

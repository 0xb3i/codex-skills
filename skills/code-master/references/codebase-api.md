# Codebase OpenAPI CLI (`scripts/codebase.py`)

纯标准库实现的 Codebase (code.byted.org) API 命令行工具，支持仓库/分支/MR 查询及 MR 行级评论。

## 目录

- 认证
- 子命令：`get-repository` / `get-branch` / `get-mr` / `get-mr-commits` / `create-comment`
- Python 直接调用

## 认证

按 [auth.md](auth.md) 使用 bytedcli 取票并在内存/子进程环境注入，不回显凭据，不用命令行 token 参数。

## 子命令

### get-repository — 获取仓库信息

```bash
python3 {SKILL_ROOT}/scripts/codebase.py get-repository \
  --path "<repo_path>"      # 例如 "pdi-qa/agent_report_service"

# 或通过仓库 ID 查询
python3 {SKILL_ROOT}/scripts/codebase.py get-repository \
  --id "<repo_id>"

# 可选：同时返回权限信息
python3 {SKILL_ROOT}/scripts/codebase.py get-repository \
  --path "<repo_path>" --with-permissions
```

从返回 JSON 的 `Result.Repository.Id` 字段取得 `repo_id`。

### get-branch — 获取分支信息

```bash
python3 {SKILL_ROOT}/scripts/codebase.py get-branch \
  --repo-id "<repo_id>" \
  --name "<branch_name>"
```

返回 JSON 中包含分支的最新 commit 信息（`Result.Branch.Commit.Id` 等）。

### get-mr — 获取 Merge Request 详情

```bash
python3 {SKILL_ROOT}/scripts/codebase.py get-mr \
  --repo-id "<repo_id>" \
  --number <mr_number>

# 可选：同时返回 commits 列表
python3 {SKILL_ROOT}/scripts/codebase.py get-mr \
  --repo-id "<repo_id>" \
  --number <mr_number> \
  --with-commits
```

返回 JSON 示例（含 `--with-commits` 时的关键字段）：

```json
{
  "Result": {
    "MergeRequest": {
      "SourceBranch": "feature/xxx",
      "TargetBranch": "master",
      "Commits": [
        {"Id": "abc1234"},
        {"Id": "def5678"}
      ]
    }
  }
}
```

- `from_commit` = `Commits` 列表中**最早**那条的 `Id`（列表末尾，时间最早）
- `to_commit` = `Commits` 列表中**最新**那条的 `Id`（列表开头，时间最近）

> 注意：若只需获取 MR 的 commit 范围，推荐使用 `get-mr-commits` 子命令，更简洁。

### get-mr-commits — 获取 MR 的 diff 范围

用户给的链接**原样**传给 `--url`（含 query 不得剥离）：带 `to_version` 时取该版本完整 diff，否则取最新版本；其余 query 参数脚本自行忽略。返回的 `diff_range` 直接作为 `--diff-range` 使用，不得重组端点或取 `^` 父提交。

`--url` 支持四类链接：

1. `https://code.byted.org/<path>/merge_requests/<num>`（codebase MR）
2. `https://bits.bytedance.net/code/<path>/merge_requests/<num>`（codebase MR 的 bits 镜像）
3. `https://bits.bytedance.net/devops/<ns>/develop/detail/<devBasicId>/change/<changeId>`（bits devops change；需 Cloud JWT）
4. `https://bits.bytedance.net/devops/<space_id>/code/detail/<clientMrId>`（bits 客户端 MR；需 Cloud JWT 与目标仓库读权限）

第 4 类客户端 MR 不在 Codebase Version 体系内，链接或 `--to-version` 带 `to_version` 会直接报错退出。

```bash
python3 {SKILL_ROOT}/scripts/codebase.py get-mr-commits --url "<mr_url>"

# 或 repo-id + MR 编号
python3 {SKILL_ROOT}/scripts/codebase.py get-mr-commits \
  --repo-id "<repo_id>" --number <mr_number> [--to-version <n>]
```

返回字段：`diff_range`（直接使用）；`from_commit` / `to_commit`（仅用于下面的回退）；`to_version`（实际使用的版本号）。

> 浅克隆下三点范围若报 `no merge base`，改用 `<from_commit>..<to_commit>`；`from_commit` 已是平台计算的 merge 基点。
> 端点不在本地（`git diff` 报 `bad object`，老版本链接常见）时，先 `git fetch origin <from_commit> <to_commit>` 再重跑。

### create-comment

在 MR 上创建行级评论。发布授权、版本检查和去重先遵循 [mr-comments.md](mr-comments.md)。以下 `--url` 自动推断示例仅用于了解接口；正式发布应显式传审查时绑定的 repo/MR/base/source 四个 Id，避免版本漂移。直接传 `--url`，脚本会内部调 `get-repository` + `get-mr --with-versions`，自动推断 `repo_id` / `commentable_id` 以及最新 Version 的 base/source commit，避免手动串联多次 API。第 4 类（bits 客户端 MR）链接同样支持，需 Cloud JWT 与目标仓库读权限。

| 参数               | 必填                  | 说明                                              |
| ------------------ | --------------------- | ------------------------------------------------- |
| `--url`            | 推荐                  | MR 链接；传入后下面 4 个 ID 都可省略，自动推断    |
| `--repo-id`        | 不传 `--url` 时必填   | 仓库 ID                                           |
| `--commentable-id` | 不传 `--url` 时必填   | MR 内部 ID（= `get-mr` 返回的 `Result.MergeRequest.Id`，非 Number） |
| `--old-commit-id`  | 不传 `--url` 时必填   | Old commit ID（默认为所选版本的 `from_commit`，规则同 `get-mr-commits`）  |
| `--new-commit-id`  | 不传 `--url` 时必填   | New commit ID（默认为所选版本的 `to_commit`，规则同 `get-mr-commits`）|
| `--content`        | 是                    | 评论内容                                          |
| `--path`           | 是                    | 文件路径                                          |
| `--start-line`     | 是                    | 起始行号                                          |
| `--end-line`       | 是                    | 结束行号                                          |

> `--url` 传入后，Old/New commit 随链接的版本参数落在用户所看的版本。仍可显式提供任一 ID 覆盖自动推断值。

```bash
# 推荐：通过 MR URL 一步打评论
python3 {SKILL_ROOT}/scripts/codebase.py create-comment \
  --url "https://code.byted.org/pdi-qa/agent_report_service/merge_requests/696" \
  --content "此处存在并发安全问题" \
  --path "src/service/user.go" \
  --start-line 42 \
  --end-line 45

# 需要精确控制时，也可显式传所有 ID
python3 {SKILL_ROOT}/scripts/codebase.py create-comment \
  --repo-id "123456" \
  --commentable-id "789" \
  --content "此处存在并发安全问题" \
  --old-commit-id "abc123" \
  --new-commit-id "def456" \
  --path "src/service/user.go" \
  --start-line 42 \
  --end-line 45
```

## Python 直接调用

脚本中的函数可直接 import 使用，无需通过 CLI：

```python
from scripts.codebase import (
    resolve_jwt,
    resolve_cloud_jwt,
    get_repository,
    get_branch,
    get_merge_request,
    get_mr_commits,
    create_comment,
    parse_mr_url,
    parse_mr_to_version,
    parse_change_url,
    parse_client_mr_url,
    select_version_range,
)

jwt = resolve_jwt()  # 从环境变量读取

# 获取 MR commit 范围（支持全部四类 URL）
commits = get_mr_commits(url="https://code.byted.org/org/repo/merge_requests/123", jwt_token=jwt)
# {"from_commit": "...", "to_commit": "...", "diff_range": "...", "to_version": 14}
# 指定版本：URL 带 ?to_version=12，或显式传 to_version=12

# 创建行级评论
create_comment(
    repo_id="123456",
    commentable_id="789",
    content="问题描述",
    old_commit_id=commits["from_commit"],
    new_commit_id=commits["to_commit"],
    path="src/file.go",
    start_line=10,
    end_line=12,
    jwt_token=jwt,
)
```

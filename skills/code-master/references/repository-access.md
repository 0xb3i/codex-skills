# 仓库访问

使用目标平台已有 CLI、宿主连接器或本地 Git 获取仓库与 MR/PR。先读取当前工具帮助和实际返回结构，按平台语义识别仓库、分支、commit、评论与状态。

## Git 与 GitHub

本地仓库用 `git status`、`git remote -v`、`git log` 和 `git diff` 确认状态、来源与范围。只 fetch 所需远端引用。审查历史版本时准备固定 commit 的隔离 checkout；不能切换或清理用户正在修改的工作区。

GitHub 可使用已安装并登录的 `gh`：

```bash
gh pr view <PR URL> --json number,url,state,baseRefName,headRefName,baseRefOid,headRefOid,headRepository,headRepositoryOwner,files
```

从返回值记录仓库、PR 编号、base/head SHA、分支和状态。缺失本地对象时 fetch 对应引用并核实 SHA；分支名不能代替固定版本。GitHub 的 PR diff 使用 base 与 head 的共同祖先到 head 的三点比较。

读取评论时区分普通 issue comments、行级 review comments 和 review threads。GitHub REST 接口可用 `gh api --paginate` 获取全部分页；review threads 的解决状态与过期状态通过 GraphQL 读取，并沿 `pageInfo.endCursor` 翻页直到 `hasNextPage=false`。平台返回不完整时补查，不能把首屏当成全部历史。

## 其他平台

使用其现有 CLI 或当前宿主连接器，取得等价的目标仓库、source/target commit、状态和全部线程。按实际文档核对版本绑定、评论锚点和分页规则。平台没有提供版本字段或解决状态时说明限制，发布前仍需验证最新源码与既有评论。

鉴权沿用当前登录配置；不打印凭据或把 token 放入命令参数、日志和仓库。读取或授权失败时先处理实际原因，不用另一个身份或假响应替代。

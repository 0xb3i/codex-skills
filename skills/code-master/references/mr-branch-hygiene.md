# MR 分支整理

用于创建 MR、更新已有 MR、目标分支前进或 MR diff 出现历史改动时。目标不是只消除冲突，而是让最新目标分支到源分支的三点 diff 精确等于本任务交付。

## 不变量

- 先 `git fetch`，按[仓库访问](repository-access.md)从 MR 元数据读取当前 source、target 和两端 commit；不要依赖陈旧的本地远端引用。
- 每次修改开放 MR 后、提交或推送前，以及发现远端 target OID 变化时，自动重新 fetch 并执行本流程；默认自行 rebase/replay、解决可依据代码契约判断的冲突并完成验证，不把常规同步工作留给用户提醒或确认。只有冲突涉及无法从需求和仓库证据确定的业务取舍，或需要新增权限时才停下来询问。
- 只变基任务源分支，绝不 rebase 目标分支、保护分支或其他共享分支。
- 工作区修改、未跟踪文件和已有本地提交都视为用户工作，按仓库规则保护；不能用 `reset --hard`、清理或覆盖来换取干净分支。
- 在改写前记录远端 source OID，并创建可恢复的本地备份 ref。已发布分支推送时只用绑定该 OID 的 `--force-with-lease`；远端已变化就停止，重新取数和复核，不能覆盖协作者更新。

## 识别本任务提交

1. 以用户需求、MR 首个可信版本、任务开始时记录的基线和实际 patch 为依据建立任务提交集合。作者、时间、分支名或“只在 source 一侧”都不能单独证明归属。
2. 用 `git log --reverse <target>...<source>`、`git cherry -v <target> <source>`、patch-id 和文件内容交叉检查。目标分支重建、回退或 squash 后，旧目标提交可能重新出现在 source-only 列表；这类历史漂移不能算作本任务改动。
3. 对每个待保留提交说明它对应哪项任务需求；无法归因的提交默认不进入 MR，先核实而不是顺手携带。

## 对齐方式

- 默认把确认后的任务提交 rebase/replay 到最新 target。线性且仅含任务提交时可直接 rebase；包含 merge commit、重复 patch 或无关提交时，基于最新 target 重建源分支，只按原顺序 replay 经确认的任务提交。
- 冲突按当前目标分支契约解决，不能整块选择 ours/theirs 后静默丢掉任一侧仍有效的行为。解决后重新检查调用方、消费者和测试。
- 若仓库规则或用户明确要求 merge-only，可 merge 最新 target；但 merge 不会自动去掉 source 历史中的无关提交。最终 diff 仍不纯净时必须先整理任务提交，不能以“冲突已解”交付。

## 推送前硬门槛

同时满足后才能提交或推送：

1. `git merge-base --is-ancestor <latest-target> <source>` 成功。
2. `git diff --name-status <latest-target>...<source>` 和完整 diff 只含本任务文件与行为；逐项解释任何看似历史遗留的改动。
3. `git log --cherry-pick --right-only <latest-target>...<source>` 中没有无法归因的提交；不能只看 mergeable 状态或提交标题。
4. 完成目标测试、静态检查和提交前审查，工作区无本次临时产物。
5. 推送前再次确认 target/source 远端 OID；推送后回读 MR 新版本，核对 target/source commit、changed files 和 mergeability。目标分支在过程中再次前进则自动重新执行本流程，直到 MR 基于最新 target 且 diff 纯净，不能仅汇报“目标又更新了”等待用户再次催促。

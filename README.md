# Codex Skills

这个仓库用于在不同电脑之间同步选定的个人通用 Codex skills。公司内部、机器专用或场景过窄的 skills 不放进来。

技能放在 `skills/<skill-name>` 目录中，包含 `SKILL.md` 和所需的引用文件、脚本、评测案例或资源。

## 维护规则

- 以当前 Codex 激活列表为对比范围，不将磁盘中未激活的技能视为当前版本。
- 仓库与激活列表重合的技能，以当前激活版本完整复写，包括正文和配套资源；不同步缓存、临时文件或凭据。
- 仓库存在、当前 Codex 未激活的技能，按旧版删除。
- 当前激活、仓库尚未收录的技能，先列出候选，仅新增用户选中的技能，不全量同步。
- 公开副本同步前检查隐私与内部资料；`writing-style` 保留当前写作规则，对真实姓名、私有资料入口及内部案例数据脱敏。本地激活版本保持原样。
- 同名技能有多个来源时，先确认来源再同步；内置和插件技能通常由原安装方式维护。

## 安装与更新

首次克隆：

```bash
git clone https://github.com/0xb3i/codex-skills.git ~/codex-skills
```

后续更新：

```bash
git -C ~/codex-skills pull --ff-only
```

克隆或更新后，逐个同步仓库托管的技能：

```bash
mkdir -p ~/.codex/skills
for skill_dir in ~/codex-skills/skills/*; do
  [ -d "$skill_dir" ] && [ -f "$skill_dir/SKILL.md" ] || continue
  skill_name=$(basename "$skill_dir")
  mkdir -p "$HOME/.codex/skills/$skill_name"
  rsync -a --delete --exclude __pycache__ --exclude '*.pyc' --exclude .DS_Store \
    "$skill_dir/" "$HOME/.codex/skills/$skill_name/"
done
```

此命令完整覆盖同名技能目录，保留未被仓库托管的本地技能。仓库删除旧技能后，另一台电脑上的对应目录不会自动删除，应在确认该技能已停用后单独清理。

这些技能面向 Codex 环境。`self-improve-skills` 在创建技能时需要宿主提供 `skill-creator`；`data-organizer` 在涉及源码迁移时使用 `code-master`，本仓库已收录该技能。

## 从当前电脑更新仓库

确认目标技能已激活且在托管范围内，再完整同步该目录：

```bash
skill_name='data-organizer'  # 替换为要更新的技能名称
rsync -a --delete --exclude __pycache__ --exclude '*.pyc' --exclude .DS_Store \
  "$HOME/.codex/skills/$skill_name/" "$HOME/codex-skills/skills/$skill_name/"
git -C ~/codex-skills add "skills/$skill_name"
git -C ~/codex-skills commit -m "update $skill_name"
git -C ~/codex-skills push
```

共享安装或插件提供的技能应使用激活列表中实际指向的源目录，不能假定它们均位于 `~/.codex/skills`。

## Skills 清单

| Skill | 用途 |
| --- | --- |
| `data-organizer` | 整理数据、文档、报告与审阅产物，改善目录、命名和查找方式。 |
| `mistake-notebook` | 将长期用户偏好、项目约束和有证据的决策原则写入适用的 `AGENTS.md`。 |
| `self-improve-skills` | 根据执行证据维护技能规则、脚本与验证流程。 |
| `code-master` | 按工程契约实现、修复和审查代码，处理已有审查意见。 |
| `ui-standards` | 为界面、图表和文档布局提供信息呈现与验收规范。 |
| `writing-style` | 按受众和场景检查文风、组织、事实依据及信息呈现。 |

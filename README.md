# Codex Skills

这个仓库用于在不同电脑之间同步个人通用 Codex skills。公司内部、机器专用或场景过窄的 skills 不放进来。

仓库里的 skills 放在 `skills/<skill-name>` 目录下，每个目录通常包含一个 `SKILL.md` 和该 skill 需要的引用文件、脚本或资源。

## 同步到另一台电脑

首次安装或全量覆盖仓库托管的 skills：

```bash
git clone https://github.com/0xb3i/codex-skills.git ~/codex-skills
mkdir -p ~/.codex/skills
rsync -a --delete --exclude .git ~/codex-skills/skills/ ~/.codex/skills/
```

之后更新：

```bash
git -C ~/codex-skills pull --ff-only
rsync -a --delete --exclude .git ~/codex-skills/skills/ ~/.codex/skills/
```

上面的命令会让 `~/.codex/skills` 与本仓库完全一致。若另一台电脑还有本仓库之外的本地私有 skills，改用逐个复制：

```bash
for skill in data-organizer docx-template-fill focused-output mistake-notebook polishing-feishu-docs self-improve-skills; do
  rsync -a --delete ~/codex-skills/skills/$skill/ ~/.codex/skills/$skill/
done
```

如果在某台电脑上修改了 skill：

```bash
rsync -a --delete ~/.codex/skills/<skill-name>/ ~/codex-skills/skills/<skill-name>/
git -C ~/codex-skills add skills/<skill-name>
git -C ~/codex-skills commit -m "update <skill-name>"
git -C ~/codex-skills push
```

## Skills 清单

| Skill | 用途 |
| --- | --- |
| `data-organizer` | 整理混乱的数据目录或工作区，进行归档、重命名、分组、扁平化、合并索引和清理临时文件。 |
| `docx-template-fill` | 填写现有 Word `.docx` 模板、表单、访谈模板或问卷，同时尽量保留原始版式、字体、边框和页面布局。 |
| `focused-output` | 优化面向用户的回答、解释、摘要、建议、分析、状态更新、代码审查和最终回复。 |
| `mistake-notebook` | 在发现反复出错、用户纠正、隐藏坑点或可能复发的问题时，判断并更新全局或项目级 `AGENTS.md`。 |
| `polishing-feishu-docs` | 将粗糙的 Feishu/Lark 文档材料润色为更适合汇报的文档，包含结构调整、结论提炼、表格、标注和流程图建议。 |
| `self-improve-skills` | 复盘并改进已有 Codex skill，在发现遗漏触发、失败路径、边界情况或过时说明时做最小必要更新。 |

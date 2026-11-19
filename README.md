<p align="center">
  <img src=".github/assets/readme-header.svg" alt="Codex Skills — 代码、设计与写作的可复用工作流" width="100%">
</p>

<p align="center">
  面向 Codex 的精选 Skills，覆盖代码开发、中文写作、界面规范与技能维护。
</p>

<p align="center">
  <a href="https://github.com/0xb3i/codex-skills/actions/workflows/validate.yml"><img src="https://github.com/0xb3i/codex-skills/actions/workflows/validate.yml/badge.svg?branch=main" alt="技能校验"></a>&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="#技能">浏览技能</a>&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="AGENTS.md">全局约定</a>&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="#开始使用">开始使用</a>&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="CONTRIBUTING.md">参与贡献</a>&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://github.com/0xb3i/codex-skills/commits/main">更新记录</a>
</p>

## 技能

| 技能 | 用途 |
| :--- | :--- |
| [**code-master**](skills/code-master/SKILL.md) | 代码实现与审查，处理 review 意见，维护工程契约。 |
| [**ui-standards**](skills/ui-standards/SKILL.md) | 界面与图表的信息呈现、配色和桌面验收规范。 |
| [**writing-style**](skills/writing-style/SKILL.md) | 中文写作与润色，检查文风、结构和事实依据。 |
| [**data-organizer**](skills/data-organizer/SKILL.md) | 整理数据与文档，优化命名、目录和资料查找。 |
| [**mistake-notebook**](skills/mistake-notebook/SKILL.md) | 将长期偏好和项目约束沉淀到 `AGENTS.md`。 |
| [**self-improve-skills**](skills/self-improve-skills/SKILL.md) | 根据执行证据改进技能，维护评测集与回归流程。 |

全局约定保存在 [AGENTS.md](AGENTS.md)，包含语言偏好、规则归属、交付方式和用户改动保护。

## 开始使用

在 Codex 任务中指定技能，例如 `$writing-style 润色这份报告`。

安装命令适用于 macOS / Linux，需要 Git 和 rsync。

<details>
<summary><strong>安装到当前电脑</strong></summary>

```bash
git clone https://github.com/0xb3i/codex-skills.git ~/codex-skills

for skill_dir in ~/codex-skills/skills/*; do
  [ -f "$skill_dir/SKILL.md" ] || continue
  skill_name=$(basename "$skill_dir")
  mkdir -p "$HOME/.codex/skills/$skill_name"
  rsync -a --delete --exclude __pycache__ --exclude '*.pyc' --exclude .DS_Store \
    "$skill_dir/" "$HOME/.codex/skills/$skill_name/"
done
```

完整覆盖这六个同名技能，保留其他本地技能。只安装部分技能时，将循环路径改为所选技能目录。

后续更新先运行 `git -C ~/codex-skills pull --ff-only`，再执行上面的同步循环。

</details>

<details>
<summary><strong>同步全局约定</strong></summary>

```bash
codex_dir="${CODEX_HOME:-$HOME/.codex}"
mkdir -p "$codex_dir"
cp -n ~/codex-skills/AGENTS.md "$codex_dir/AGENTS.md"
```

首次配置会复制全局约定；已有 `AGENTS.md` 时保留原文件，按需合并仓库版本。公开副本省略内部服务和配置定位信息。

</details>

`code-master` 的内部代码平台适配需要对应环境；`self-improve-skills` 创建技能时使用 Codex 内置的 `skill-creator`。

---

欢迎通过 [Issues](https://github.com/0xb3i/codex-skills/issues) 反馈问题，通过 [Pull Request](https://github.com/0xb3i/codex-skills/pulls) 改进技能。贡献方式见 [CONTRIBUTING.md](CONTRIBUTING.md)。

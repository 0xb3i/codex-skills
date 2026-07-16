---
name: sync-codex-skills
description: Use when a user wants to sync, push, pull, mirror, back up, restore, or test one specific Codex skill with a server through a shared Git repo such as dotfiles-codex; use after any Codex skill is edited or updated to check whether that skill is managed and auto-sync it in the right direction.
---

# Sync Codex Skills

用 Git repo 做唯一真相，同步 `skills/<skill-name>`；脚本只提交指定 skill，让另一端 fast-forward 更新，并只给该 skill 建单独 symlink。被这个 skill 维护过的 skill 记录在 `managed-skills.json`。

## 默认约定

- 本机 repo：`~/dotfiles-codex`
- 服务端 repo：`~/dotfiles-codex`
- repo 内目录：`skills/<skill-name>`
- 本机 `~/.codex/skills` 应指向或等价于 `~/dotfiles-codex/skills`
- 服务端不整体替换 `~/.codex/skills`；只在缺失时创建 `~/.codex/skills/<skill-name>` symlink
- 登记表：`managed-skills.json`，分 `local_to_remote` 和 `remote_to_local` 两个列表
- skill 名只接受小写字母、数字、连字符

## 命令

以下 `python3 scripts/...` 命令默认在本 Skill 目录 `~/.codex/skills/sync-codex-skills` 下执行；在其他目录执行时使用脚本绝对路径。

如果本机还没有 repo，只 bootstrap 这一个 skill：

```bash
mkdir -p ~/dotfiles-codex/skills
cp -R ~/.codex/skills/mistake-notebook ~/dotfiles-codex/skills/
git -C ~/dotfiles-codex init -b main
git -C ~/dotfiles-codex remote add origin cloudide-wsed9ab0d425c9aa57:dotfiles-codex.git
```

如果服务端用 bare repo，首次推送前先建 bare repo；推送后 clone 工作树：

```bash
ssh cloudide-wsed9ab0d425c9aa57 'git init --bare ~/dotfiles-codex.git'
ssh cloudide-wsed9ab0d425c9aa57 'git --git-dir=~/dotfiles-codex.git symbolic-ref HEAD refs/heads/main'
ssh cloudide-wsed9ab0d425c9aa57 'git clone ~/dotfiles-codex.git ~/dotfiles-codex'
```

不要 `rm -rf ~/.codex/skills`，也不要整体 symlink 覆盖远端 skills；已有远端 skill 必须保留。

先 dry-run 看将执行的命令：

```bash
python3 scripts/sync_codex_skills.py push --skill mistake-notebook --server user@server --dry-run
```

本机推到服务端：

```bash
python3 scripts/sync_codex_skills.py push --skill mistake-notebook --server user@server --message "update mistake-notebook"
```

成功执行 `push` 后，脚本自动把该 skill 记录进 `local_to_remote`。

服务端反向同步回本机：

```bash
python3 scripts/sync_codex_skills.py pull --skill mistake-notebook --server user@server --message "update mistake-notebook from server"
```

成功执行 `pull` 后，脚本自动把该 skill 记录进 `remote_to_local`。

任意 skill 更新后，先触发本 skill 并运行 auto；没登记就不动作：

```bash
python3 scripts/sync_codex_skills.py auto --skill mistake-notebook --dry-run
python3 scripts/sync_codex_skills.py auto --skill mistake-notebook --message "auto sync mistake-notebook"
```

`auto` 默认判断当前环境：本机 repo 存在就按本地处理；否则服务端 repo 存在就按远端处理。远端侧只提交并 push 到 origin，不尝试反连本机。

查看登记表：

```bash
python3 scripts/sync_codex_skills.py list
```

repo 路径不同时显式传入：

```bash
python3 scripts/sync_codex_skills.py push --skill my-skill --repo ~/dotfiles-codex --server user@server --server-repo ~/dotfiles-codex
```

注意：`--server-repo` 如果包含 `~`，在本机 shell 里加引号，例如 `--server-repo '~/dotfiles-codex'`。

## 边界

- 用 `git pull --ff-only`，分叉历史直接失败，人工处理后再同步。
- 不自动创建远端 repo、不处理批量同步、不做文件监听 daemon。
- ponytail: 单 repo 管全部 skills；需要多 repo、多环境矩阵或自动冲突解决时再加配置层。

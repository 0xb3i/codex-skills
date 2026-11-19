#!/usr/bin/env python3
"""Read-only cross-skill audit; use skill-creator for per-skill authoring checks."""

import argparse
from collections import defaultdict
import os
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit

try:
    import yaml
    from markdown_it import MarkdownIt
except ImportError as exc:
    raise SystemExit("缺少审计依赖，请在所用 Python 环境安装 PyYAML 和 markdown-it-py。") from exc


def read_config(path):
    if not path.exists():
        return {}
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError as exc:
            raise ValueError("Python < 3.11 读取配置需要 tomli。") from exc
    with path.open("rb") as stream:
        return tomllib.load(stream)


def local_targets(text):
    """Parse actual Markdown links; code samples are not dependencies."""
    for token in MarkdownIt().parse(text):
        for child in token.children or []:
            attribute = "href" if child.type == "link_open" else "src" if child.type == "image" else None
            if attribute is None:
                continue
            target = child.attrGet(attribute)
            if not target:
                continue
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            path = unquote(parsed.path)
            if any(marker in path for marker in ("${", "<", ">")):
                continue
            yield path


def audit(roots, config):
    errors, notes = [], []
    names = defaultdict(list)
    entries = {}
    for root in roots:
        if not root.is_dir():
            errors.append(f"技能根目录不存在：{root}")
            continue
        for entry in sorted(root.glob("*/SKILL.md")):
            entries.setdefault(entry.resolve(), entry)

    links_checked = 0
    for resolved, entry in entries.items():
        try:
            text = entry.read_text(encoding="utf-8")
            parts = text.split("---", 2)
            if len(parts) != 3 or parts[0].strip():
                raise ValueError("缺少 YAML frontmatter")
            metadata = yaml.safe_load(parts[1])
            if not isinstance(metadata, dict):
                raise ValueError("frontmatter 必须是映射")
            for field in ("name", "description"):
                if not isinstance(metadata.get(field), str) or not metadata[field].strip():
                    raise ValueError(f"{field} 必须是非空字符串")
            names[metadata["name"]].append(resolved)
            ui = entry.parent / "agents/openai.yaml"
            if ui.exists() and not isinstance(yaml.safe_load(ui.read_text()), dict):
                raise ValueError("agents/openai.yaml 必须是映射")
        except (OSError, ValueError, yaml.YAMLError) as exc:
            errors.append(f"{entry}：{exc}")
            continue

        # Only follow documentation reachable from the entrypoint. Unlinked historical
        # notes and examples are not assumed to be part of the execution instructions.
        pending = [entry]
        visited = set()
        while pending:
            document = pending.pop()
            identity = document.resolve()
            if identity in visited:
                continue
            visited.add(identity)
            try:
                body = document.read_text(encoding="utf-8")
                if body.startswith("---\n"):
                    body = body.split("---", 2)[-1]
                for target in local_targets(body):
                    destination = Path(target).expanduser()
                    if not destination.is_absolute():
                        destination = document.parent / destination
                    links_checked += 1
                    if not destination.exists():
                        errors.append(f"失效引用：{document} → {target}")
                    elif destination.suffix == ".md" and destination.resolve().is_relative_to(entry.parent.resolve()):
                        pending.append(destination)
            except (OSError, ValueError) as exc:
                errors.append(f"无法检查引用 {document}：{exc}")

    for name, paths in sorted(names.items()):
        if len(paths) > 1:
            errors.append(f"同名技能 {name}：" + "；".join(map(str, paths)))

    for setting in config.get("skills", {}).get("config", []):
        if not isinstance(setting, dict) or not setting.get("path"):
            continue
        path = Path(setting["path"]).expanduser()
        if not path.exists():
            if setting.get("enabled", True):
                errors.append(f"配置启用了不存在的技能：{path}")
            else:
                notes.append(f"保留的禁用项（路径当前不存在，不自动删除）：{path}")
    return len(entries), links_checked, sorted(set(errors)), sorted(set(notes))


def main():
    codex_root = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    parser = argparse.ArgumentParser(description="只读检查技能重名、元数据、本地 Markdown 引用和启用配置；不评判语义边界。")
    parser.add_argument("--root", action="append", type=Path, help="技能根目录，可重复；默认检查用户和共享技能")
    parser.add_argument("--config", type=Path, default=codex_root / "config.toml")
    parser.add_argument("--no-config", action="store_true", help="仅检查指定目录，适用于隔离验证")
    args = parser.parse_args()
    roots = args.root or [codex_root / "skills", Path.home() / ".agents/skills"]
    try:
        config = {} if args.no_config else read_config(args.config.expanduser())
        count, links, errors, notes = audit([root.expanduser() for root in roots], config)
    except (OSError, ValueError) as exc:
        print(f"检查失败：{exc}", file=sys.stderr)
        return 2
    print(f"检查 {count} 个独立技能、{links} 个本地引用：{len(errors)} 个错误。")
    for error in errors:
        print(f"错误：{error}")
    for note in notes:
        print(f"提示：{note}")
    print("范围：本地技能目录；不扫描插件市场、不改启用状态、不执行技能。语义边界仍需人工或独立场景审查。")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

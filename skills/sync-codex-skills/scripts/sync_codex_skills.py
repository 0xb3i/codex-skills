#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys


SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_./~:@+-]+$")
SAFE_SKILL = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DEFAULT_MANIFEST = Path(__file__).resolve().parent.parent / "managed-skills.json"


def empty_manifest():
    return {"local_to_remote": {}, "remote_to_local": {}}


def load_manifest(path=DEFAULT_MANIFEST):
    path = Path(path)
    if not path.exists():
        return empty_manifest()
    manifest = json.loads(path.read_text())
    manifest.setdefault("local_to_remote", {})
    manifest.setdefault("remote_to_local", {})
    return manifest


def save_manifest(manifest, path=DEFAULT_MANIFEST):
    path = Path(path)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def register_skill(manifest, direction, skill, repo, server, server_repo):
    if direction not in {"push", "pull"}:
        raise ValueError("direction must be push or pull")
    bucket = "local_to_remote" if direction == "push" else "remote_to_local"
    manifest[bucket][skill] = {"repo": repo, "server": server, "server_repo": server_repo}
    return manifest


def detect_side(entry):
    if Path(os.path.expanduser(entry["repo"])).exists():
        return "local"
    if Path(os.path.expanduser(entry["server_repo"])).exists():
        return "remote"
    return "local"


def safe_token(value):
    if not SAFE_TOKEN.fullmatch(value):
        raise ValueError(f"unsafe shell token: {value!r}")
    return value


def plan_commands(direction, skill, repo, server, server_repo, message):
    if not SAFE_SKILL.fullmatch(skill):
        raise ValueError("skill must be lowercase letters, digits, and hyphens")
    skill_path = f"skills/{skill}" if skill else "skills"
    remote_repo = safe_token(server_repo)
    remote_skill = safe_token(skill_path)
    remote_link = f"mkdir -p ~/.codex/skills && test -e ~/.codex/skills/{skill} || ln -s {remote_repo}/{remote_skill} ~/.codex/skills/{skill}"
    remote_message = "'" + message.replace("'", "'\\''") + "'"
    if direction == "push":
        return [
            ["git", "-C", repo, "add", skill_path],
            ["git", "-C", repo, "commit", "-m", message],
            ["git", "-C", repo, "push", "-u", "origin", "HEAD"],
            ["ssh", server, f"cd {remote_repo} && git pull --ff-only"],
            ["ssh", server, remote_link],
        ]
    if direction == "pull":
        remote = " && ".join(
            [
                f"cd {remote_repo}",
                f"git add {remote_skill}",
                f"git commit -m {remote_message}",
                "git push",
            ]
        )
        return [
            ["ssh", server, remote],
            ["git", "-C", repo, "pull", "--ff-only"],
        ]
    raise ValueError(f"unknown direction: {direction}")


def plan_remote_publish_commands(skill, server_repo, message):
    if not SAFE_SKILL.fullmatch(skill):
        raise ValueError("skill must be lowercase letters, digits, and hyphens")
    skill_path = f"skills/{skill}"
    return [
        ["git", "-C", server_repo, "add", skill_path],
        ["git", "-C", server_repo, "commit", "-m", message],
        ["git", "-C", server_repo, "push", "-u", "origin", "HEAD"],
    ]


def plan_auto_commands(manifest, skill, side, message):
    if side == "auto":
        entry = manifest["local_to_remote"].get(skill) or manifest["remote_to_local"].get(skill)
        if not entry:
            return []
        side = detect_side(entry)
    if side == "local" and skill in manifest["local_to_remote"]:
        entry = manifest["local_to_remote"][skill]
        return plan_commands("push", skill, entry["repo"], entry["server"], entry["server_repo"], message)
    if side == "local" and skill in manifest["remote_to_local"]:
        entry = manifest["remote_to_local"][skill]
        return plan_commands("pull", skill, entry["repo"], entry["server"], entry["server_repo"], message)
    if side == "remote" and skill in manifest["remote_to_local"]:
        entry = manifest["remote_to_local"][skill]
        return plan_remote_publish_commands(skill, entry["server_repo"], message)
    return []


def format_commands(commands, dry_run=False):
    if dry_run:
        return json.dumps(commands, ensure_ascii=False, indent=2)
    return "\n".join(" ".join(command) for command in commands)


def run(command):
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode == 0:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        return

    output = result.stdout + result.stderr
    if command[0] == "git" and "commit" in command and "nothing to commit" in output:
        print(output, end="")
        return
    if command[0] == "ssh" and "nothing to commit" in output:
        print(output, end="")
        return
    print(output, end="", file=sys.stderr)
    raise SystemExit(result.returncode)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sync one Codex skill through a shared Git repo.")
    parser.add_argument("direction", choices=["push", "pull", "auto", "list"])
    parser.add_argument("--skill", help="Skill folder name under skills/.")
    parser.add_argument("--repo", default="~/dotfiles-codex", help="Local Git repo that contains skills/.")
    parser.add_argument("--server", help="SSH target, for example user@example.com.")
    parser.add_argument("--server-repo", default="~/dotfiles-codex", help="Server Git repo path.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Managed skills registry JSON.")
    parser.add_argument("--side", choices=["auto", "local", "remote"], default="auto", help="Current environment for auto sync.")
    parser.add_argument("--message", help="Commit message.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned commands as JSON.")
    args = parser.parse_args(argv)

    manifest = load_manifest(args.manifest)
    if args.direction == "list":
        print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if not args.skill:
        parser.error("--skill is required unless direction is list")
    if args.direction in {"push", "pull"} and not args.server:
        parser.error("--server is required for push or pull")

    message = args.message or f"sync {args.skill}"
    repo = os.path.expanduser(args.repo)
    commands = (
        plan_auto_commands(manifest, args.skill, args.side, message)
        if args.direction == "auto"
        else plan_commands(args.direction, args.skill, repo, args.server, args.server_repo, message)
    )
    if args.dry_run:
        print(format_commands(commands, dry_run=True))
        return
    for command in commands:
        run(command)
    if args.direction in {"push", "pull"}:
        register_skill(manifest, args.direction, args.skill, repo, args.server, args.server_repo)
        save_manifest(manifest, args.manifest)


if __name__ == "__main__":
    main()

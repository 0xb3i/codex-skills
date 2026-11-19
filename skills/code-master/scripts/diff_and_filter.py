#!/usr/bin/env python3
"""
diff_and_filter.py — 执行 git diff、过滤待评审文件，并完成自定义 workflow preflight。

一次调用默认会输出以下产物：
  - diff_files.md：原始变更文件列表
  - review_files.md：过滤后的待评审文件列表
  - custom_workflows.json：仓库级自定义 workflow 列表
  - codespec_pe.md：若命中 codespec workflow，则额外准备本地检测指令

用法:
    python3 diff_and_filter.py --diff-range <range> --repo-root <path> --output-dir <dir>

示例:
    python3 diff_and_filter.py \
        --diff-range "HEAD~1..HEAD" \
        --repo-root /path/to/repo \
        --output-dir /tmp/myrepo_1234

退出码约定：仅 diff 过滤本身失败（必选步骤）时返回非 0；集成 preflight 的
可选资源（自定义 workflow、codespec 规则）拉取失败不阻塞，记日志并把对应
workflow 标记 status=skipped 后正常返回 0。
"""

import argparse
import fnmatch
import json
import os
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import PurePosixPath
from typing import Dict, List, Optional, Tuple

# ---------- 排除规则 ----------

BUILD_DIRS = {"dist", "build", "out", "target", "bin"}

LOCK_FILES = {
    "go.sum",
    "go.mod",
    "go.mod.properties",
    "go.work",
    "gradle.properties",
    "package-lock.json",
    "yarn.lock",
    "Podfile.lock",
    "pnpm-lock.yaml",
    "Cargo.lock",
    "uv.lock",
}

IDE_DIRS = {".idea", ".vscode"}
IDE_FILES = {".editorconfig"}
IDE_EXTS = {".iml"}

# AI 工具/Agent 配置目录
AGENT_DIRS = {".agents", ".claude", ".coco", ".cursor", ".trae"}

# Thrift/Protobuf IDL 文件
IDL_EXTS = {".thrift", ".proto"}

BINARY_EXTS = {
    # 图片
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".svg",
    # 字体
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    # Office/PDF
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    # 可执行/库
    ".exe", ".so", ".dylib", ".dll", ".a", ".lib",
    ".app", ".bin", ".war",
    # 压缩/打包
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".egg", ".jar", ".nar", ".tgz", ".xz", ".zst",
    # 音视频
    ".mp3", ".mp4", ".avi", ".mov", ".wav",
    ".ogg", ".webm",
    # 编译产物
    ".pyc", ".class", ".o", ".obj",
    ".pyd", ".pyo",
    # 纯文档/数据
    ".md", ".markdown", ".mdown", ".mdpolicy", ".mdwn",
    ".mkd", ".mkdn", ".mkdown",
    ".rest", ".rst",
    ".rtf", ".txt",
    ".csv", ".tsv",
    ".log", ".lst",
    ".dat", ".db",
    ".pickle", ".pkl",
    ".json", ".sql", ".xml", ".yaml", ".yml",
    # Web 静态资产（.min.js 走 basename 规则）
    ".css", ".less",
    # Unity/Game
    ".fbx", ".anim", ".asmdef", ".asset", ".bundle", ".controller",
    ".lighting", ".mat", ".mesh", ".meta", ".playable", ".rendertexture",
    ".shadervariants", ".signal", ".spriteatlas", ".unity", ".wproj", ".wwu",
    # ML 模型
    ".h5", ".keras", ".model", ".onnx", ".pb", ".pt", ".pth",
    # 杂项
    ".glif", ".lo", ".mine", ".p", ".pro", ".rkt", ".snap", ".ss",
}

VENDOR_DIRS = {"vendor", "node_modules", "third_party", "external", "third_deps", "GloryPacketCapture", "xtern"}

SKIP_BASENAMES = {"LICENSE"}

# 生成/脚手架/RPC 目录
GENERATED_DIRS = {
    "__test__", "__tests__",
    "__mock__", "__mocks__", "mock", "mocks",
    "bam", "bam-auto-generate",
    "gen", "idl",
    "kitex_gen", "kitty_context", "kitty_server",
    "pb_gen", "pk_gen", "rpc_gen", "rpcauto",
    "test", "tests",
    "thrift_gen", "thrift_models",
}

GENERATED_DIR_PREFIXES = ("auto-generate",)

GENERATED_SUBPATHS = (
    ("rpc", "clients"),
    ("rpc", "plugin"),
    ("rpc", "rpc"),
    ("rpc", "rpcauto"),
)


# ---------- 路径工具 ----------

def _segments(path: str) -> Tuple[str, ...]:
    return PurePosixPath(path).parts


def _basename(path: str) -> str:
    return PurePosixPath(path).name


def _ext(path: str) -> str:
    return PurePosixPath(path).suffix.lower()


# ---------- 语言识别 ----------

_LANG_BY_EXT = {
    ".go": "Go",
    ".py": "Python",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".java": "Java",
    ".kt": "Kotlin", ".kts": "Kotlin",
    ".rs": "Rust",
    ".c": "C", ".h": "C",
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".hpp": "C++", ".hh": "C++",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".m": "Objective-C", ".mm": "Objective-C",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".sql": "SQL",
    ".md": "Markdown",
    ".yml": "YAML", ".yaml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
    ".xml": "XML",
    ".html": "HTML", ".htm": "HTML",
    ".css": "CSS", ".scss": "SCSS", ".sass": "SCSS", ".less": "CSS",
    ".vue": "Vue",
    ".thrift": "Thrift",
    ".proto": "Protobuf",
    ".scala": "Scala",
    ".lua": "Lua",
    ".dart": "Dart",
    ".r": "R",
    ".ex": "Elixir", ".exs": "Elixir",
    ".hs": "Haskell",
}

_LANG_BY_BASENAME = {
    "makefile": "Makefile",
    "dockerfile": "Dockerfile",
    "rakefile": "Ruby",
    "gemfile": "Ruby",
}


def detect_language(filepath: str) -> str:
    base = _basename(filepath).lower()
    if base in _LANG_BY_BASENAME:
        return _LANG_BY_BASENAME[base]
    ext = _ext(filepath)
    if ext in _LANG_BY_EXT:
        return _LANG_BY_EXT[ext]
    return "Other"


# ---------- 排除判断 ----------

def _is_build_artifact(path: str) -> bool:
    return bool(BUILD_DIRS & set(_segments(path)))


def _is_lock_file(path: str) -> bool:
    name = _basename(path)
    if name in LOCK_FILES:
        return True
    if name.endswith(".lock") or name.endswith(".lockb"):
        return True
    return False


_GENERATED_BASENAMES = {"facade.go", "idls.go", "kite.go", "wire.go"}
_GENERATED_SUFFIXES = (
    ".pb.go", "_gen.go", ".gen.go", "_generated.go",
    ".mock.go", ".thrift.go", "_bos.go",
    "_test.go",
    ".testio",
    ".pbtxt", ".pbdata", ".pbbin",
    "_tobedeleted",
)


def _is_generated_code(path: str) -> bool:
    name = _basename(path)
    if name in _GENERATED_BASENAMES:
        return True
    if any(name.endswith(suf) for suf in _GENERATED_SUFFIXES):
        return True
    if ".generated." in name:
        return True
    if name.startswith("mock_") and name.endswith(".go"):
        return True
    return False


def _is_misc_skip(path: str) -> bool:
    name = _basename(path)
    if name in SKIP_BASENAMES:
        return True
    if name.endswith(".min.js"):
        return True
    return False


def _is_generated_dir(path: str) -> bool:
    segs = _segments(path)
    if GENERATED_DIRS & set(segs):
        return True
    for seg in segs:
        for pref in GENERATED_DIR_PREFIXES:
            if seg.startswith(pref):
                return True
    for sub in GENERATED_SUBPATHS:
        n = len(sub)
        for i in range(len(segs) - n + 1):
            if tuple(segs[i:i + n]) == sub:
                return True
    return False


def _is_ide_config(path: str) -> bool:
    if IDE_DIRS & set(_segments(path)):
        return True
    if _basename(path) in IDE_FILES:
        return True
    if _ext(path) in IDE_EXTS:
        return True
    return False


def _is_agent_config(path: str) -> bool:
    return bool(AGENT_DIRS & set(_segments(path)))


def _is_idl_file(path: str) -> bool:
    return _ext(path) in IDL_EXTS


def _is_binary_media(path: str) -> bool:
    return _ext(path) in BINARY_EXTS


def _is_vendor(path: str) -> bool:
    return bool(VENDOR_DIRS & set(_segments(path)))


def _is_hidden(path: str) -> bool:
    return any(seg.startswith(".") for seg in _segments(path))


EXCLUDE_RULES: List[Tuple[str, object]] = [
    ("构建产物", lambda p, s: _is_build_artifact(p)),
    ("依赖/包管理", lambda p, s: _is_lock_file(p)),
    ("自动生成代码", lambda p, s: _is_generated_code(p)),
    ("IDE/编辑器配置", lambda p, s: _is_ide_config(p)),
    ("AI 工具/Agent 配置", lambda p, s: _is_agent_config(p)),
    ("Thrift/Protobuf IDL", lambda p, s: _is_idl_file(p)),
    ("二进制/媒体文件", lambda p, s: _is_binary_media(p)),
    ("Vendor/第三方", lambda p, s: _is_vendor(p)),
    ("生成/测试目录", lambda p, s: _is_generated_dir(p)),
    ("许可证/压缩资源", lambda p, s: _is_misc_skip(p)),
    ("隐藏文件/目录", lambda p, s: _is_hidden(p)),
    ("删除的文件", lambda p, s: s == "D"),
]


# ---------- 远程排除规则 ----------

_REMOTE_CONFIG_URL = "https://9abqm0rn.fn.bytedance.net/smart/cr/flux_review_config"
_REMOTE_TIMEOUT = 5

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


def _run_git_silent(args: List[str], cwd: Optional[str] = None) -> str:
    try:
        result = subprocess.run(
            ["git"] + args, cwd=cwd,
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _parse_repo_from_remote(remote: str) -> str:
    if not remote:
        return ""
    s = remote.strip()
    if s.endswith(".git"):
        s = s[:-4]
    if "://" not in s and ":" in s and "@" in s:
        s = s.split(":", 1)[1]
    else:
        s = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", "", s)
        if "/" in s:
            parts = s.split("/", 1)
            if "." in parts[0] or "@" in parts[0]:
                s = parts[1] if len(parts) > 1 else parts[0]
    s = s.strip("/")
    segments = [seg for seg in s.split("/") if seg]
    if len(segments) >= 2:
        return "/".join(segments[-2:])
    return ""


def _get_repo_name(repo_root: str) -> str:
    remote = _run_git_silent(["remote", "get-url", "origin"], cwd=repo_root)
    if not remote:
        remotes = _run_git_silent(["remote"], cwd=repo_root)
        first = (remotes.splitlines() or [""])[0].strip()
        if first:
            remote = _run_git_silent(["remote", "get-url", first], cwd=repo_root)
    return _parse_repo_from_remote(remote)


def _get_target_branch(repo_root: str) -> str:
    branch = _run_git_silent(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
    if branch == "HEAD":
        return ""
    return branch


def fetch_remote_exclusions(repo_root: str) -> List[str]:
    """从远程接口拉取项目级排除 glob 列表。

    返回去掉 '-' 前缀后的 glob 模式列表。
    任何异常都吞掉返回空列表，不影响主流程。
    """
    _log_prefix = "[remote-exclusion]"
    try:
        repo_name = _get_repo_name(repo_root)
        if not repo_name:
            print(f"{_log_prefix} 无法解析 repo_name，跳过远程排除")
            return []

        branch = _get_target_branch(repo_root)
        print(f"{_log_prefix} repo={repo_name}, branch={branch or '(empty, default master)'}")

        params = f"repo_name={urllib.parse.quote(repo_name, safe='')}"
        if branch:
            params += f"&target_branch={urllib.parse.quote(branch, safe='')}"

        url = f"{_REMOTE_CONFIG_URL}?{params}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=_REMOTE_TIMEOUT, context=_ssl_ctx) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))

        paths = body.get("paths")
        if not paths or not isinstance(paths, list):
            print(f"{_log_prefix} paths 为空或非列表，跳过")
            return []

        exclusions = []
        for p in paths:
            if isinstance(p, str) and p.startswith("-"):
                exclusions.append(p[1:])

        print(f"{_log_prefix} 解析到 {len(exclusions)} 条排除模式")
        return exclusions
    except Exception as e:
        print(f"{_log_prefix} Warning: 拉取远程排除规则失败 ({e})，使用本地规则继续", file=sys.stderr)
        return []


# ---------- Git 操作 ----------

def _run_git(repo_root: str, args: List[str]) -> subprocess.CompletedProcess:
    """在 repo_root 下执行 git 命令。"""
    if not os.path.isdir(repo_root):
        print(f"Error: --repo-root 路径不存在或不是目录: {repo_root}", file=sys.stderr)
        sys.exit(1)

    cmd = ["git"] + args
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, cwd=repo_root, check=False,
        )
    except FileNotFoundError:
        print("Error: git 不在 PATH 中", file=sys.stderr)
        sys.exit(1)


def get_diff_files(repo_root: str, diff_range: str) -> List[Tuple[str, str]]:
    """运行 git diff --name-status，返回 [(status, filepath), ...]。"""
    proc = _run_git(repo_root, ["diff", "--name-status", diff_range])
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        print(f"Error: git diff --name-status 失败: {stderr}", file=sys.stderr)
        sys.exit(1)

    files = []
    for line in proc.stdout.strip().splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        status, filepath = parts[0].strip(), parts[1].strip()
        # 状态码可能带数字（如 R100），取首字母
        status = status[0] if status else "M"
        files.append((status, filepath))
    return files


def get_line_stats(repo_root: str, diff_range: str) -> Dict[str, Tuple[int, int]]:
    """运行 git diff --numstat，返回 {filepath: (added, deleted)}。"""
    proc = _run_git(repo_root, ["diff", "--numstat", diff_range])
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        if stderr:
            print(f"Warning: git diff --numstat 失败: {stderr}", file=sys.stderr)
        return {}

    stats: Dict[str, Tuple[int, int]] = {}
    for line in proc.stdout.strip().splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        added_str, deleted_str, filepath = parts
        added = int(added_str) if added_str != "-" else 0
        deleted = int(deleted_str) if deleted_str != "-" else 0
        stats[filepath] = (added, deleted)
    return stats


# ---------- 过滤逻辑 ----------

def apply_exclusions(
    files: List[Tuple[str, str]],
    line_stats: Dict[str, Tuple[int, int]],
    remote_exclusions: Optional[List[str]] = None,
) -> Tuple[List[Tuple[str, str]], Dict[str, List[str]]]:
    """
    对文件列表应用排除规则。

    返回:
        kept: 保留的文件列表
        excluded_by_category: {类别名: [filepath, ...]}
    """
    kept = []
    excluded_by_category: Dict[str, List[str]] = {}
    _remote_patterns = remote_exclusions or []

    for status, filepath in files:
        excluded = False

        for category, matcher in EXCLUDE_RULES:
            if matcher(filepath, status):
                excluded_by_category.setdefault(category, []).append(filepath)
                excluded = True
                break

        if not excluded and _remote_patterns:
            for pattern in _remote_patterns:
                if fnmatch.fnmatch(filepath, pattern):
                    excluded_by_category.setdefault("远程配置排除", []).append(filepath)
                    excluded = True
                    break

        if not excluded:
            added, deleted = line_stats.get(filepath, (0, 0))
            if added == 0 and deleted == 0:
                excluded_by_category.setdefault("空文件", []).append(filepath)
                excluded = True

        if not excluded:
            kept.append((status, filepath))

    return kept, excluded_by_category


# ---------- 输出文件生成 ----------

def write_diff_files(
    output_path: str,
    files: List[Tuple[str, str]],
    diff_range: str,
) -> None:
    """写入 diff_files.md（原始变更文件列表）。"""
    lines = [
        "# Diff 文件列表",
        "",
        f"范围: {diff_range}",
        "diff_direction: base → source（`-` 行 = 旧代码/已删除，`+` 行 = 新代码/待评审）",
        "",
        "| 状态 | 文件路径 |",
        "| ---- | -------- |",
    ]
    for status, filepath in files:
        lines.append(f"| {status}    | {filepath} |")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_review_files(
    output_path: str,
    kept: List[Tuple[str, str]],
    line_stats: Dict[str, Tuple[int, int]],
    total: int,
    excluded_by_category: Dict[str, List[str]],
) -> None:
    """写入 review_files.md（过滤后的待评审文件列表）。"""
    excluded_total = sum(len(v) for v in excluded_by_category.values())

    if excluded_total == 0:
        summary = "排除文件数: 0"
    else:
        parts = [f"{cat} {len(fs)} 个" for cat, fs in excluded_by_category.items()]
        summary = f"排除文件数: {excluded_total}（{', '.join(parts)}）"

    lines = [
        "# 待评审文件列表",
        "",
        "scope: diff_only",
        "",
        "diff_direction: base → source（`-` 行 = 旧代码/已删除，`+` 行 = 新代码/待评审）",
        "",
        f"总文件数: {total}",
        summary,
        "",
        "| 文件路径 | 变更行数 |",
        "| -------- | -------- |",
    ]

    for status, filepath in kept:
        added, deleted = line_stats.get(filepath, (0, 0))
        lines.append(f"| {filepath} | +{added}, -{deleted} |")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_diff_stats(
    output_path: str,
    diff_range: str,
    all_files: List[Tuple[str, str]],
    kept: List[Tuple[str, str]],
    line_stats: Dict[str, Tuple[int, int]],
    excluded_by_category: Dict[str, List[str]],
    started_at_epoch: float,
    finished_at_epoch: float,
) -> None:
    """写入 diff_stats.json（完整 CR 规模/语言/耗时指标，供本地报告和诊断使用）。"""
    diff_added = sum(s[0] for s in line_stats.values())
    diff_deleted = sum(s[1] for s in line_stats.values())

    review_added = 0
    review_deleted = 0
    review_files: List[Dict[str, object]] = []
    language_distribution: Dict[str, int] = {}
    for status, filepath in kept:
        added, deleted = line_stats.get(filepath, (0, 0))
        review_added += added
        review_deleted += deleted
        language = detect_language(filepath)
        language_distribution[language] = language_distribution.get(language, 0) + 1
        review_files.append({
            "path": filepath,
            "status": status,
            "added": added,
            "deleted": deleted,
            "language": language,
        })

    excluded_by_reason = {cat: len(fs) for cat, fs in excluded_by_category.items()}
    excluded_total = sum(excluded_by_reason.values())

    stats = {
        "diff_range": diff_range,
        "started_at_epoch": int(started_at_epoch),
        "finished_at_epoch": int(finished_at_epoch),
        "timings_ms": {
            "diff_filter": int((finished_at_epoch - started_at_epoch) * 1000),
        },
        "diff_files_total": len(all_files),
        "review_files_total": len(kept),
        "excluded_files_total": excluded_total,
        "excluded_by_reason": excluded_by_reason,
        "diff_added_lines": diff_added,
        "diff_deleted_lines": diff_deleted,
        "diff_changed_lines": diff_added + diff_deleted,
        "review_added_lines": review_added,
        "review_deleted_lines": review_deleted,
        "review_changed_lines": review_added + review_deleted,
        "language_distribution": language_distribution,
        "review_files": review_files,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False)
        f.write("\n")


def run_integrated_preflight(args: argparse.Namespace, output_dir: str) -> None:
    """在 diff 过滤完成后继续执行统一 preflight（可选资源，失败不阻塞）。"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    preflight_script = os.path.join(script_dir, "codespec_preflight.py")
    cmd = [
        sys.executable,
        preflight_script,
        "--output-dir",
        output_dir,
        "--repo-root",
        args.repo_root,
    ]
    if args.repo:
        cmd += ["--repo", args.repo]
    if args.git_remote:
        cmd += ["--git-remote", args.git_remote]
    if args.workflow_endpoint:
        cmd += ["--workflow-endpoint", args.workflow_endpoint]
    if args.codespec_endpoint:
        cmd += ["--codespec-endpoint", args.codespec_endpoint]
    if args.comment_lang:
        cmd += ["--comment-lang", args.comment_lang]
    print("[diff_and_filter] review_files.md 已生成，开始执行集成 preflight")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    for stream in (proc.stdout, proc.stderr):
        for line in stream.splitlines():
            if line.strip():
                print(line)
    if proc.returncode != 0:
        # preflight 只准备可选资源，失败不阻塞主流程；兜底保证
        # custom_workflows.json 存在，下游按未配置自定义工作流处理。
        print(
            f"[diff_and_filter] 集成 preflight 未成功（exit_code={proc.returncode}），"
            "不阻塞主流程，自定义工作流按未配置处理",
            file=sys.stderr,
        )
        workflows_path = os.path.join(output_dir, "custom_workflows.json")
        if not os.path.exists(workflows_path):
            try:
                with open(workflows_path, "w", encoding="utf-8") as f:
                    json.dump({"repo": "", "workflows": []}, f, ensure_ascii=False, indent=2)
                print(f"[custom-workflows] 已写入空 workflow 列表兜底: {workflows_path}")
            except Exception as e:
                print(f"[custom-workflows] 写空 workflow 列表失败: {e}", file=sys.stderr)


# ---------- CLI ----------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="执行 git diff、过滤待评审文件，并完成自定义 workflow preflight"
    )
    parser.add_argument(
        "--diff-range", required=True,
        help="git diff 范围（如 HEAD~1..HEAD、commit1..commit2、branch1...branch2）",
    )
    parser.add_argument(
        "--repo-root", required=True, help="仓库根目录路径",
    )
    parser.add_argument(
        "--output-dir", required=True, help="输出目录路径（写入 diff/review 文件，并承接 workflow/codespec 预检产物）",
    )
    parser.add_argument("--repo", default=None, help="仓库标识 org/repo，透传给集成 preflight")
    parser.add_argument("--git-remote", default=None, help="git remote 值，透传给集成 preflight")
    parser.add_argument("--workflow-endpoint", default=None, help="自定义工作流接口 base url，透传给集成 preflight")
    parser.add_argument("--codespec-endpoint", default=None, help="codespec query_spec_skills 接口 url，透传给集成 preflight")
    parser.add_argument("--comment-lang", default="zh", choices=["zh", "en"], help="codespec 检测指令评论语言")
    args = parser.parse_args()

    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    diff_files_path = os.path.join(output_dir, "diff_files.md")
    review_files_path = os.path.join(output_dir, "review_files.md")
    diff_stats_path = os.path.join(output_dir, "diff_stats.json")

    started_at = time.time()
    print(f"[diff_and_filter] 开始执行, diff_range={args.diff_range}, repo_root={args.repo_root}, output_dir={output_dir}")

    # 1. 获取变更文件列表
    files = get_diff_files(args.repo_root, args.diff_range)
    if not files:
        print("Warning: diff 范围内没有变更文件", file=sys.stderr)
        # 仍然输出空文件以保持流程一致
        write_diff_files(diff_files_path, [], args.diff_range)
        write_review_files(review_files_path, [], {}, 0, {})
        try:
            write_diff_stats(
                diff_stats_path, args.diff_range,
                [], [], {}, {},
                started_at, time.time(),
            )
        except Exception as e:
            print(f"Warning: 写入 diff_stats.json 失败 ({e})，不影响主流程", file=sys.stderr)
        print("Diff: 0 files | Review: 0 files")
        print(f"[diff_and_filter] 执行结束, 耗时 {time.time() - started_at:.2f}s")
        return 0

    # 2. 写入 diff_files.md
    write_diff_files(diff_files_path, files, args.diff_range)

    # 3. 获取行数统计
    line_stats = get_line_stats(args.repo_root, args.diff_range)

    # 3.5 拉取远程排除规则
    remote_exclusions = fetch_remote_exclusions(args.repo_root)

    # 4. 过滤文件
    total = len(files)
    kept, excluded_by_category = apply_exclusions(files, line_stats, remote_exclusions)

    # 5. 写入 review_files.md 和 diff_stats.json
    write_review_files(review_files_path, kept, line_stats, total, excluded_by_category)
    try:
        write_diff_stats(
            diff_stats_path, args.diff_range,
            files, kept, line_stats, excluded_by_category,
            started_at, time.time(),
        )
    except Exception as e:
        print(f"Warning: 写入 diff_stats.json 失败 ({e})，不影响主流程", file=sys.stderr)

    # 6. 输出摘要
    excluded_total = sum(len(v) for v in excluded_by_category.values())
    total_added = sum(s[0] for s in line_stats.values())
    total_deleted = sum(s[1] for s in line_stats.values())
    print(f"Diff: {total} files (+{total_added}, -{total_deleted}) | Review: {len(kept)} files, {excluded_total} excluded")

    if len(kept) == 0:
        print("Warning: 所有文件均被排除，待评审文件为 0", file=sys.stderr)
        for cat, cat_files in excluded_by_category.items():
            for fp in cat_files:
                print(f"  [{cat}] {fp}", file=sys.stderr)

    run_integrated_preflight(args, output_dir)
    print(f"[diff_and_filter] 执行结束, 耗时 {time.time() - started_at:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())

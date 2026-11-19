#!/usr/bin/env python3
"""自定义 workflow 与 codespec 资源预检（单入口）。

一次调用完成：自定义 workflow 拉取（调用 fetch_custom_workflows.py）、codespec
类型 workflow 判定、codespec 资源目录初始化（拉取 spec_rule.md 与 skill 包）、
本地检测指令渲染和摘要打印。未配置 codespec 类型 workflow 时，仅完成自定义
workflow 拉取并跳过 codespec 资源准备。

退出码约定：可选资源（自定义 workflow、codespec 规则、检测指令）拉取失败或为空
一律不阻塞——记日志、把对应 workflow 回写标记 status=skipped 后正常退出（exit 0），
由派发侧跳过被标记的条目（派发即资源就绪）。

codespec 资源初始化逻辑参考 fluxcr build/init_sandbox.py::download_spec_skills；
检测指令渲染按 fluxcr buildCodeSpecInputs 语义注入 code_spec_rules / comment_lang。
"""

import argparse
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple

# codespec 规则拉取端点，可被环境变量覆盖
DEFAULT_CODESPEC_ENDPOINT = "https://dataflow.bytedance.net/ake/code_quality/query_spec_skills"
CODESPEC_ENDPOINT_ENV = "BITS_CODE_GUARD_CODESPEC_ENDPOINT"
META_FILENAME = "codespec_meta.json"
SPEC_RULE_FILENAME = "spec_rule.md"
PE_FILENAME = "codespec_pe.md"
DEBUG_DIRNAME = "debug"

# HTTP 重试配置（移植 fluxcr init_sandbox._urlopen_with_retry）
HTTP_TIMEOUT = 30
HTTP_MAX_RETRIES = 3
HTTP_BACKOFF_BASE = 2
HTTP_DOWNLOAD_CHUNK_SIZE = 1024 * 1024
_RETRYABLE_HTTP_CODES = {502, 503, 504, 429}

# ---------- SSL ----------
# 内部站点可能使用自签/内部 CA，与既有脚本（fetch_custom_workflows.py / codebase.py）保持一致，
# 关闭证书校验，避免本机 CA bundle 不信任导致拉取失败。
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


# ========== 通用工具 ==========

def run_step(args: List[str]) -> int:
    result = subprocess.run(args, capture_output=True, text=True)
    for stream in (result.stdout, result.stderr):
        for line in stream.splitlines():
            if line.strip():
                print(line)
    return result.returncode


def write_debug_text(output_dir: str, filename: str, content: str) -> Optional[str]:
    """写 codespec/debug 下的调试文件。失败只记 stderr，不影响主流程。"""
    try:
        debug_dir = Path(output_dir) / "codespec" / DEBUG_DIRNAME
        debug_dir.mkdir(parents=True, exist_ok=True)
        out_path = debug_dir / filename
        out_path.write_text(content, encoding="utf-8")
        return str(out_path)
    except Exception as e:
        print(f"[codespec] 写 debug/{filename} 失败: {e}", file=sys.stderr)
        return None


def write_debug_json(output_dir: str, filename: str, data: dict) -> Optional[str]:
    return write_debug_text(output_dir, filename, json.dumps(data, ensure_ascii=False, indent=2))


def append_debug_log(output_dir: str, message: str) -> None:
    try:
        debug_dir = Path(output_dir) / "codespec" / DEBUG_DIRNAME
        debug_dir.mkdir(parents=True, exist_ok=True)
        with (debug_dir / "codespec_debug.log").open("a", encoding="utf-8") as f:
            f.write(message.rstrip() + "\n")
    except Exception as e:
        print(f"[codespec] 写 debug/codespec_debug.log 失败: {e}", file=sys.stderr)


def read_meta(meta_path: Path) -> dict:
    if not meta_path.exists():
        return {}
    return json.loads(meta_path.read_text(encoding="utf-8"))


def write_meta(output_dir: str, meta: dict) -> Optional[str]:
    try:
        codespec_dir = Path(output_dir) / "codespec"
        codespec_dir.mkdir(parents=True, exist_ok=True)
        out_path = codespec_dir / META_FILENAME
        out_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(out_path)
    except Exception as e:
        print(f"[codespec] 写 {META_FILENAME} 失败: {e}", file=sys.stderr)
        return None


def find_codespec_workflow_idx(workflows_path: Path) -> Optional[int]:
    data = json.loads(workflows_path.read_text(encoding="utf-8"))
    workflows = data.get("workflows") or []
    if not workflows:
        return None
    for idx, workflow in enumerate(workflows):
        text = ((workflow.get("name") or "") + "\n" + (workflow.get("content") or "")).lower()
        if "codespec" in text or "code_spec" in text or "devspec" in text:
            return idx
    return None


def write_empty_workflows_file(workflows_path: Path) -> None:
    """兜底写空 workflow 列表，保证下游读取行为确定（按未配置自定义工作流处理）。"""
    payload = {"repo": "", "workflows": []}
    try:
        workflows_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[custom-workflows] 已写入空 workflow 列表兜底: {workflows_path}")
    except Exception as exc:
        print(f"[custom-workflows] 写空 workflow 列表失败: {exc}", file=sys.stderr)


def mark_workflow_skipped(workflows_path: Path, idx: int, reason: str) -> None:
    """把资源不可用的 workflow 回写标记为 skipped。

    派发侧只派发未标记 skipped 的条目（派发即资源就绪）：subagent 拿到任务时
    检测资源必然完整，不存在进场后才发现资源为空的空跑。
    """
    try:
        data = json.loads(workflows_path.read_text(encoding="utf-8"))
        workflows = data.get("workflows") or []
        workflows[idx]["status"] = "skipped"
        workflows[idx]["skip_reason"] = reason
        workflows_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[custom-workflows] workflow idx={idx} 标记 status=skipped: {reason}")
    except Exception as exc:
        print(f"[custom-workflows] 标记 workflow idx={idx} skipped 失败: {exc}", file=sys.stderr)


def print_summary(meta_path: Path, debug_dir: Path) -> None:
    meta = read_meta(meta_path)
    print(
        "[codespec] preflight summary: "
        f"repo={meta.get('repo', '')}, "
        f"rule_count={meta.get('rule_count', 0)}, "
        f"pe_source={meta.get('pe_source', '')}, "
        f"debug_dir={meta.get('debug_dir', str(debug_dir))}, "
        f"error={meta.get('error', '')}"
    )


# ========== git 仓库标识解析（对齐 fetch_custom_workflows.py 的实现） ==========

def run_git(args: List[str], repo_root: Optional[str] = None) -> str:
    try:
        cmd = ["git"]
        if repo_root:
            cmd += ["-C", repo_root]
        result = subprocess.run(
            cmd + args,
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except Exception:
        return ""


def get_git_remote_url(repo_root: Optional[str] = None) -> str:
    try:
        url = run_git(["remote", "get-url", "origin"], repo_root)
        if url:
            return url
        remotes = run_git(["remote"], repo_root)
        if not remotes:
            return ""
        lines = remotes.splitlines()
        if not lines:
            return ""
        first = lines[0].strip()
        if not first:
            return ""
        return run_git(["remote", "get-url", first], repo_root)
    except Exception:
        return ""


def parse_repo_from_remote(remote: str) -> str:
    """从 git remote url 解析出 `org/repo`。解析不出时返回空串。"""
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


def resolve_repo(repo_arg: Optional[str], git_remote_arg: Optional[str], repo_root: Optional[str] = None) -> str:
    """按优先级解析仓库标识：--repo > --git-remote 解析 > repo_root 下 git remote 解析。"""
    if repo_arg and repo_arg.strip():
        return repo_arg.strip()
    if git_remote_arg and git_remote_arg.strip():
        parsed = parse_repo_from_remote(git_remote_arg)
        return parsed if parsed else git_remote_arg.strip()
    remote = get_git_remote_url(repo_root)
    if remote:
        parsed = parse_repo_from_remote(remote)
        return parsed if parsed else remote
    return ""


# ========== HTTP 重试（移植 fluxcr init_sandbox） ==========

def _is_retryable(e: Exception) -> bool:
    if isinstance(e, urllib.error.HTTPError):
        return e.code in _RETRYABLE_HTTP_CODES
    if isinstance(e, (urllib.error.URLError, OSError)):
        return True
    return False


def _urlopen_with_retry(req, timeout=HTTP_TIMEOUT, max_retries=HTTP_MAX_RETRIES):
    for attempt in range(1, max_retries + 1):
        try:
            return urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
            if _is_retryable(e) and attempt < max_retries:
                wait = HTTP_BACKOFF_BASE ** attempt
                print(f"[codespec] request failed (attempt {attempt}/{max_retries}): {e}, "
                      f"retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("request failed before any attempt was made")


def _download_to(url: str, dest: str) -> None:
    """下载远程文件写入 dest，带指数退避重试。"""
    last_error = None
    for attempt in range(1, HTTP_MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url.strip(), method="GET")
            with _urlopen_with_retry(req, max_retries=1) as resp, open(dest, "wb") as out:
                while True:
                    chunk = resp.read(HTTP_DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    out.write(chunk)
            return
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
            last_error = e
            if _is_retryable(e) and attempt < HTTP_MAX_RETRIES:
                wait = HTTP_BACKOFF_BASE ** attempt
                print(f"[codespec] download failed (attempt {attempt}/{HTTP_MAX_RETRIES}): {e}, "
                      f"retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                break
    try:
        print(f"[codespec] urllib 下载失败，尝试 curl fallback: {last_error}", file=sys.stderr)
        cmd = [
            "curl",
            "-q",
            "--noproxy",
            "*",
            "--fail",
            "--silent",
            "--show-error",
            "--location",
            "--max-time",
            str(HTTP_TIMEOUT),
            "--output",
            dest,
            url.strip(),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=HTTP_TIMEOUT + 5)
        return
    except Exception:
        if last_error:
            raise last_error
        raise


def _post_json_with_curl(endpoint: str, payload: bytes, log_id: str = "") -> Tuple[str, dict]:
    """用系统 curl POST JSON。用于 urllib 在受限运行环境 DNS/代理异常时兜底。"""
    cmd = [
        "curl",
        "-q",
        "--noproxy",
        "*",
        "--silent",
        "--show-error",
        "--location",
        "--max-time",
        str(HTTP_TIMEOUT),
        "--header",
        "Content-Type: application/json",
    ]
    if log_id:
        cmd += ["--header", f"x-tt-logid: {log_id}"]
    cmd += ["--data-binary", "@-", endpoint]
    result = subprocess.run(
        cmd,
        input=payload,
        capture_output=True,
        timeout=HTTP_TIMEOUT + 5,
    )
    debug = {
        "curl_command": "curl -q --noproxy '*' --silent --show-error --location --max-time <timeout> --header 'Content-Type: application/json' --data-binary @- <endpoint>",
        "curl_returncode": result.returncode,
        "curl_stderr": result.stderr.decode("utf-8", errors="replace"),
    }
    if result.returncode != 0:
        raise RuntimeError(debug["curl_stderr"] or f"curl exited with {result.returncode}")
    return result.stdout.decode("utf-8", errors="replace"), debug


def fetch_repo_data(endpoint: str, repo: str) -> Tuple[Optional[dict], str, dict]:
    """POST 拉取 codespec 规则数据。返回 (repo_data, error, debug)，任何异常吞掉转 error 字符串。"""
    payload = json.dumps({"repos": [repo]}).encode("utf-8")
    debug = {
        "endpoint": endpoint,
        "request_payload": {"repos": [repo]},
        "response_raw": "",
        "response_json": None,
        "repo": repo,
    }
    req = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    log_id = os.environ.get("LOG_ID", "").strip()
    if log_id:
        req.add_header("x-tt-logid", log_id)
        debug["x_tt_logid"] = log_id

    try:
        with _urlopen_with_retry(req) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            debug["http_status"] = getattr(resp, "status", None)
            debug["transport"] = "urllib"
    except (urllib.error.URLError, OSError) as e:
        debug["urllib_error"] = str(e)
        try:
            print(f"[codespec] urllib 请求失败，尝试 curl fallback: {e}", file=sys.stderr)
            raw, curl_debug = _post_json_with_curl(endpoint, payload, log_id)
            debug.update(curl_debug)
            debug["transport"] = "curl"
        except Exception as curl_error:
            debug["curl_error"] = str(curl_error)
            debug["error"] = str(e)
            return None, f"请求 codespec 规则接口失败: {e}; curl fallback 失败: {curl_error}", debug
    except Exception as e:
        debug["urllib_error"] = str(e)
        try:
            print(f"[codespec] urllib 请求异常，尝试 curl fallback: {e}", file=sys.stderr)
            raw, curl_debug = _post_json_with_curl(endpoint, payload, log_id)
            debug.update(curl_debug)
            debug["transport"] = "curl"
        except Exception as curl_error:
            debug["curl_error"] = str(curl_error)
            debug["error"] = str(e)
            return None, f"请求 codespec 规则接口异常: {e}; curl fallback 失败: {curl_error}", debug
    debug["response_raw"] = raw

    try:
        body = json.loads(raw)
    except Exception as e:
        debug["error"] = str(e)
        return None, f"codespec 规则接口返回非法 JSON: {e}", debug
    debug["response_json"] = body

    if body.get("code") != 0:
        return None, f"codespec 规则接口返回非成功 code={body.get('code')}, message={body.get('message', '')}", debug

    repo_data = (body.get("data") or {}).get(repo)
    if repo_data is None:
        return None, f"codespec 规则接口未返回仓库 {repo} 的数据", debug
    return repo_data, "", debug


# ========== zip 解压（zip-slip 防护 + 公共前缀剥离，移植 fetch_spec_skill.go 思路） ==========

def _detect_common_prefix(names: List[str]) -> str:
    if not names:
        return ""
    prefix = ""
    for name in names:
        parts = name.split("/", 1)
        if len(parts) < 2:
            return ""
        dir_ = parts[0] + "/"
        if prefix == "":
            prefix = dir_
        elif prefix != dir_:
            return ""
    return prefix


def _extract_zip(zip_path: str, dest_dir: str) -> None:
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        prefix = _detect_common_prefix(names)
        dest_root = os.path.abspath(dest_dir)
        for info in zf.infolist():
            name = info.filename
            if prefix:
                name = name[len(prefix):] if name.startswith(prefix) else name
                if not name:
                    continue
            target = os.path.abspath(os.path.join(dest_dir, name))
            # zip-slip 防护
            if target != dest_root and not target.startswith(dest_root + os.sep):
                continue
            if info.is_dir():
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)


def _is_safe_skill_name(skill_name: str) -> bool:
    """校验远端返回的 skill_name 是否为安全的单层文件名。

    仅允许字母、数字、下划线、连字符、点；拒绝空串、`.`/`..`、含路径分隔符或绝对路径，
    防止拼接后逃逸出 skills_root。
    """
    if not skill_name or skill_name in (".", ".."):
        return False
    if "/" in skill_name or "\\" in skill_name or os.path.isabs(skill_name):
        return False
    return re.fullmatch(r"[A-Za-z0-9._-]+", skill_name) is not None


def download_and_extract_skill(content_tos_url: str, skill_name: str, skills_root: str) -> str:
    """下载并解压单个 skill 包到 skills_root/<skill_name>/，返回目标目录。"""
    if not _is_safe_skill_name(skill_name):
        raise ValueError(f"非法 skill_name（可能导致路径逃逸）: {skill_name!r}")
    dest_dir = os.path.join(skills_root, skill_name)
    # 二次防御：确认拼接后的目标目录仍位于 skills_root 内
    skills_root_abs = os.path.abspath(skills_root)
    dest_abs = os.path.abspath(dest_dir)
    if dest_abs != skills_root_abs and not dest_abs.startswith(skills_root_abs + os.sep):
        raise ValueError(f"skill 目标目录逃逸出 skills_root: {dest_abs}")
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_zip = os.path.join(tmp_dir, "archive.zip")
        _download_to(content_tos_url, tmp_zip)
        os.makedirs(dest_dir, exist_ok=True)
        _extract_zip(tmp_zip, dest_dir)
    return dest_dir


# ========== codespec 资源目录初始化 ==========

def count_spec_rules(spec_rule_path: str) -> int:
    """统计 spec_rule.md 中的规则条目数（按 skill_name: 行计数）。"""
    try:
        with open(spec_rule_path, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for line in f if line.startswith("skill_name: "))
    except Exception:
        return 0


def init_codespec_resources(
    output_dir: str,
    repo_root: Optional[str],
    repo_arg: Optional[str],
    git_remote_arg: Optional[str],
    endpoint: str,
) -> int:
    """初始化 codespec 资源目录：拉取 spec_rule.md 与 skill 包，写 codespec_meta.json。

    可选资源缺失（未配置 / 拉取失败）返回 0，meta 记 rule_count=0 + error；
    仅调用方配置错误（仓库标识无法解析）返回非 0。
    """
    repo = resolve_repo(repo_arg, git_remote_arg, repo_root)
    codespec_dir = os.path.join(output_dir, "codespec")
    skills_root = os.path.join(codespec_dir, "skills")
    spec_rule_path = os.path.join(codespec_dir, SPEC_RULE_FILENAME)

    meta = {
        "repo": repo,
        "endpoint": endpoint,
        "spec_rule_path": "",
        "skills": [],
        "rule_count": 0,
        "error": "",
        "debug_dir": os.path.join(codespec_dir, DEBUG_DIRNAME),
    }

    if not repo:
        meta["error"] = ("无法解析仓库标识：未传 --repo/--git-remote，且在 --repo-root"
                         "（未传时为当前工作目录）下也未解析出 git remote。"
                         "请显式传入 --repo 或 --repo-root 指向目标仓库根目录。")
        write_meta(output_dir, meta)
        # 仓库标识无法解析属于调用方配置问题（cwd 不在目标仓库内 / 未传参），
        # 而非"该仓库未配置 codespec 规则"，返回非 0 让调用方显式感知。
        print(f"[codespec] {meta['error']}", file=sys.stderr)
        return 2

    repo_data, error, fetch_debug = fetch_repo_data(endpoint, repo)
    if error:
        # 仅失败路径落 debug：请求元信息、原始响应与错误日志，供排查。
        write_debug_json(output_dir, "query_spec_skills_debug.json", fetch_debug)
        if fetch_debug.get("response_raw"):
            write_debug_text(output_dir, "query_spec_skills_response.raw.json", fetch_debug["response_raw"])
        meta["error"] = error
        write_meta(output_dir, meta)
        append_debug_log(output_dir, f"query_spec_skills failed: {error}")
        # 规则拉取失败属可选资源缺失：meta 已记 rule_count=0 + error，正常返回，
        # 由主流程把该条 workflow 标记 skipped，不阻塞。
        print(f"[codespec] {error}；跳过 codespec 检测", file=sys.stderr)
        return 0

    try:
        os.makedirs(codespec_dir, exist_ok=True)
    except Exception as e:
        meta["error"] = f"创建 codespec 目录失败: {e}"
        write_meta(output_dir, meta)
        print(f"[codespec] {meta['error']}；跳过 codespec 检测", file=sys.stderr)
        return 0

    # 下载 spec_rule
    spec_tos_url = (repo_data.get("spec_tos_url") or "").strip()
    if spec_tos_url:
        try:
            _download_to(spec_tos_url, spec_rule_path)
            meta["spec_rule_path"] = spec_rule_path
            meta["rule_count"] = count_spec_rules(spec_rule_path)
        except Exception as e:
            print(f"[codespec] 下载 spec_rule 失败: {e}", file=sys.stderr)
            append_debug_log(output_dir, f"download spec_rule failed: {e}")

    # 下载并解压 skill 包
    skills_meta = []
    for skill in repo_data.get("skills", []) or []:
        if not isinstance(skill, dict):
            continue
        content_tos_url = (skill.get("content_tos_url") or "").strip()
        skill_name = (skill.get("name") or "").strip()
        if not content_tos_url or not skill_name:
            continue
        try:
            skill_dir = download_and_extract_skill(content_tos_url, skill_name, skills_root)
            skills_meta.append({"name": skill_name, "dir": skill_dir})
        except Exception as e:
            print(f"[codespec] 下载 skill {skill_name} 失败: {e}", file=sys.stderr)
            append_debug_log(output_dir, f"download skill {skill_name} failed: {e}")
    meta["skills"] = skills_meta

    # rule_count 若 spec_rule 缺失但有 skill 包，则以 skill 数兜底，确保主线能被触发
    if meta["rule_count"] == 0 and skills_meta:
        meta["rule_count"] = len(skills_meta)

    write_meta(output_dir, meta)

    if meta["rule_count"] > 0:
        print(f"[codespec] 仓库 {repo} 拉取到 {meta['rule_count']} 条 codespec 规则、"
              f"{len(skills_meta)} 个 skill 包，已写入 {codespec_dir}")
    else:
        # rule_count=0 属可选资源缺失：正常返回，由主流程标记 skipped。
        print(f"[codespec] 仓库 {repo} 未配置 codespec 规则，跳过 codespec 检测")

    return 0


# ========== 检测指令渲染 ==========

def read_template(template_path: str) -> str:
    try:
        return Path(template_path).read_text(encoding="utf-8")
    except Exception as e:
        print(f"[codespec-pe] 读取检测指令模板失败: {e}", file=sys.stderr)
        return ""


def build_code_spec_rules(spec_rule_path: str) -> str:
    """按 fluxcr buildCodeSpecInputs 语义构造 code_spec_rules 变量。"""
    try:
        content = Path(spec_rule_path).read_text(encoding="utf-8").strip()
    except Exception:
        content = ""
    if not content:
        return ""
    return f"# 业务自定义code_spec规则\n{content}"


def render_template(template: str, spec_rule_path: str, comment_lang: str) -> str:
    """渲染内置 Jinja2 检测指令模板中当前用到的变量与条件。"""
    pe_text = re.sub(r"\{\{\s*code_spec_rules\s*\}\}", build_code_spec_rules(spec_rule_path), template)

    def replace_comment_lang(match: re.Match) -> str:
        en_branch, zh_branch = match.group(1), match.group(2)
        return en_branch if comment_lang == "en" else zh_branch

    return re.sub(
        r'\{%-\s*if\s+comment_lang\s*==\s*"en"\s*%\}(.*?)\{%-\s*else\s*%\}(.*?)\{%-\s*endif\s*%\}',
        replace_comment_lang,
        pe_text,
        flags=re.DOTALL,
    )


def write_codespec_pe(output_dir: str, template_path: str, spec_rule_path: str, comment_lang: str) -> bool:
    """把渲染后的检测指令写入 codespec_pe.md。成功返回 True。"""
    pe_template = read_template(template_path)
    if not pe_template:
        return False
    pe_text = render_template(pe_template, spec_rule_path, comment_lang)
    codespec_dir = Path(output_dir) / "codespec"
    try:
        codespec_dir.mkdir(parents=True, exist_ok=True)
        (codespec_dir / PE_FILENAME).write_text(pe_text, encoding="utf-8")
        return True
    except Exception as e:
        print(f"[codespec-pe] 写 {PE_FILENAME} 失败: {e}", file=sys.stderr)
        append_debug_log(output_dir, f"write codespec 检测指令 failed: {e}")
        return False


def update_pe_meta(output_dir: str, pe_source: str, template_path: str = "") -> None:
    """把检测指令相关字段合并进 codespec_meta.json（若存在），不存在则新建最小记录。"""
    codespec_dir = Path(output_dir) / "codespec"
    meta_path = codespec_dir / META_FILENAME
    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    meta["pe_source"] = pe_source
    meta["pe_path"] = str(codespec_dir / PE_FILENAME) if pe_source != "none" else ""
    meta["pe_template"] = template_path if pe_source != "none" else ""
    try:
        codespec_dir.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[codespec-pe] 写 {META_FILENAME} 失败: {e}", file=sys.stderr)


def render_codespec_pe(output_dir: str, comment_lang: str) -> None:
    """渲染本地检测指令模板并更新 meta。模板缺失或渲染失败标记 pe_source=none，不抛出。"""
    template_path = str(Path(__file__).resolve().parent.parent / "assets" / "codespec-pe-template.md.j2")
    spec_rule = str(Path(output_dir) / "codespec" / SPEC_RULE_FILENAME)

    if write_codespec_pe(output_dir, template_path, spec_rule, comment_lang):
        update_pe_meta(output_dir, "local_template", template_path)
        print(f"[codespec-pe] 检测指令已写入 {Path(output_dir) / 'codespec' / PE_FILENAME}")
        return

    print("[codespec-pe] 本地检测指令模板不可用，检测指令内容为空", file=sys.stderr)
    append_debug_log(output_dir, "local PE template unavailable, rendered PE is empty")
    update_pe_meta(output_dir, "none")


# ========== 主流程 ==========

def main() -> int:
    parser = argparse.ArgumentParser(description="运行自定义 workflow 与 codespec 资源预检")
    parser.add_argument("--output-dir", required=True, help="WORK_DIR")
    parser.add_argument("--repo-root", required=True, help="被评审仓库根目录")
    parser.add_argument("--repo", default=None, help="仓库标识 org/repo，最高优先级")
    parser.add_argument("--git-remote", default=None, help="git remote 值，脚本负责解析成 org/repo")
    parser.add_argument("--workflow-endpoint", default=None, help="自定义工作流接口 base url")
    parser.add_argument(
        "--codespec-endpoint",
        default=os.environ.get(CODESPEC_ENDPOINT_ENV, DEFAULT_CODESPEC_ENDPOINT),
        help=f"codespec query_spec_skills 接口 url，默认 {DEFAULT_CODESPEC_ENDPOINT}，"
             f"可用环境变量 {CODESPEC_ENDPOINT_ENV} 覆盖",
    )
    parser.add_argument("--comment-lang", default="zh", choices=["zh", "en"], help="codespec 检测指令评论语言")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    output_dir = Path(args.output_dir)
    workflows_path = output_dir / "custom_workflows.json"
    meta_path = output_dir / "codespec" / META_FILENAME
    debug_dir = output_dir / "codespec" / DEBUG_DIRNAME
    output_dir.mkdir(parents=True, exist_ok=True)

    fetch_cmd = [
        sys.executable,
        str(script_dir / "fetch_custom_workflows.py"),
        "--output-dir",
        args.output_dir,
        "--repo-root",
        args.repo_root,
    ]
    if args.repo:
        fetch_cmd += ["--repo", args.repo]
    if args.git_remote:
        fetch_cmd += ["--git-remote", args.git_remote]
    if args.workflow_endpoint:
        fetch_cmd += ["--endpoint", args.workflow_endpoint]
    rc = run_step(fetch_cmd)
    if rc != 0:
        # 拉取脚本自身约定"始终 exit 0"，非 0 意味着脚本崩溃。不阻塞主流程：
        # 兜底保证 custom_workflows.json 存在，按未配置自定义工作流处理。
        print(f"[custom-workflows] 拉取脚本异常退出（rc={rc}），按未配置自定义工作流处理", file=sys.stderr)
        if not workflows_path.exists():
            write_empty_workflows_file(workflows_path)

    try:
        idx = find_codespec_workflow_idx(workflows_path)
    except Exception as exc:
        print(f"[codespec-preflight] 读取 custom_workflows.json 失败: {exc}；重写为空列表，按未配置自定义工作流处理", file=sys.stderr)
        write_empty_workflows_file(workflows_path)
        return 0
    if idx is None:
        print("[codespec-preflight] 未发现 codespec 类型 workflow，跳过 codespec 资源目录初始化与检测指令渲染")
        return 0

    try:
        rc = init_codespec_resources(
            output_dir=args.output_dir,
            repo_root=args.repo_root,
            repo_arg=args.repo,
            git_remote_arg=args.git_remote,
            endpoint=args.codespec_endpoint,
        )
    except Exception as exc:
        print(f"[codespec] 资源目录初始化异常: {exc}", file=sys.stderr)
        rc = 1
    if rc != 0:
        mark_workflow_skipped(workflows_path, idx, f"codespec 资源目录初始化失败（rc={rc}），详见 [codespec] 日志")
        print_summary(meta_path, debug_dir)
        return 0

    meta = read_meta(meta_path)
    if not meta.get("rule_count"):
        reason = meta.get("error") or "仓库未配置 codespec 规约（rule_count=0）"
        mark_workflow_skipped(workflows_path, idx, f"codespec 规则为空：{reason}")
        print_summary(meta_path, debug_dir)
        return 0

    render_codespec_pe(args.output_dir, args.comment_lang)
    meta = read_meta(meta_path)
    if meta.get("pe_source") in ("", "none"):
        mark_workflow_skipped(workflows_path, idx, "codespec 检测指令渲染失败（pe_source=none）")
        print_summary(meta_path, debug_dir)
        return 0

    print_summary(meta_path, debug_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

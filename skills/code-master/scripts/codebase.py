#!/usr/bin/env python3

import argparse
import base64
import json
import os
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

BASE_URL = "https://code.byted.org/api/v2/"
BITS_BASE_URL = "https://bits.bytedance.net"
OPTIMUS_BASE_URL = "https://optimus.bytedance.net"

# bits devops change 详情页 URL 形如：
# https://bits.bytedance.net/devops/<devops_id>/develop/detail/<dev_basic_id>/change/<change_id>
CHANGE_URL_RE = re.compile(
    r"bits\.bytedance\.net/devops/\d+/develop/detail/(\d+)/change/(\d+)"
)

# bits 客户端 MR 详情页 URL，捕获组是 Bits 客户端 MR ID（非 codebase iid）。
# 两种段序都要认：
# - 用户从地址栏粘贴：bits.bytedance.net/devops/1142536048898/code/detail/8376235?cr_tab=...
# - optimus 返回的 mr_detail_url：bits.bytedance.net/bytebus/devops/code/detail/8376235
CLIENT_MR_URL_RE = re.compile(
    r"bits\.bytedance\.net/(?:devops/\d+|[\w.-]+/devops)/code/detail/(\d+)"
)

# ---------- SSL ----------
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


# ---------- Auth ----------
_JWT_PATTERN = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")


def looks_like_jwt(token: str) -> bool:
    """快速判断字符串是否符合 JWT 的 base64url . base64url . base64url 形状。
    用于过滤 AgentBuddy CLI 把错误文本（含换行/ANSI 转义）当作 stdout 返回的情况。"""
    return bool(token) and bool(_JWT_PATTERN.match(token))


def fetch_codebase_jwt() -> str:
    """调用 AgentBuddy CLI 自动获取 Codebase JWT，优先直接命令，失败回退内部 registry 的 npx。"""
    errors: List[str] = []
    for cmd in (
        ["agentbuddy", "get-codebase-jwt"],
        ["npx", "--yes", "--registry=https://bnpm.byted.org", "agentbuddy", "get-codebase-jwt"],
    ):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=10,
            )
        except FileNotFoundError as e:
            errors.append(f"{' '.join(cmd)}: {e}")
            continue
        except subprocess.TimeoutExpired:
            errors.append(f"{' '.join(cmd)}: timeout")
            continue
        token = result.stdout.strip()
        if result.returncode == 0 and looks_like_jwt(token):
            return token
        if result.returncode == 0:
            preview = token[:80].replace("\n", "\\n")
            errors.append(
                f"{' '.join(cmd)} rc=0 but stdout is not a JWT: {preview!r}"
            )
        else:
            errors.append(
                f"{' '.join(cmd)} rc={result.returncode}: {result.stderr.strip()}"
            )
    raise RuntimeError("; ".join(errors) or "no command available")


def resolve_jwt(codebase_jwt: Optional[str] = None) -> str:
    """解析 JWT token：优先 AIME_USER_CODE_JWT 环境变量，其次命令行参数，
    再次 CODEBASE_JWT 环境变量，最后尝试通过 AgentBuddy CLI 自动获取；全部失败才报错退出。"""
    aime_token = os.environ.get("AIME_USER_CODE_JWT", "").strip()
    if aime_token:
        return aime_token
    if codebase_jwt:
        return codebase_jwt
    env_token = os.environ.get("CODEBASE_JWT")
    if env_token:
        return env_token
    try:
        return fetch_codebase_jwt()
    except Exception as e:
        print(
            "Error: 未获取到 Codebase JWT token。\n"
            "  自动获取失败: " + str(e) + "\n"
            "  可通过 --codebase-jwt 参数或 CODEBASE_JWT 环境变量手动传入。",
            file=sys.stderr,
        )
        sys.exit(1)


def fetch_cloud_jwt() -> str:
    """调用 AgentBuddy CLI 自动获取 Cloud JWT，优先直接命令，失败回退内部 registry 的 npx。"""
    errors: List[str] = []
    for cmd in (
        ["agentbuddy", "get-jwt"],
        ["npx", "--yes", "--registry=https://bnpm.byted.org", "agentbuddy", "get-jwt"],
    ):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=10,
            )
        except FileNotFoundError as e:
            errors.append(f"{' '.join(cmd)}: {e}")
            continue
        except subprocess.TimeoutExpired:
            errors.append(f"{' '.join(cmd)}: timeout")
            continue
        token = result.stdout.strip()
        if result.returncode == 0 and looks_like_jwt(token):
            return token
        if result.returncode == 0:
            preview = token[:80].replace("\n", "\\n")
            errors.append(
                f"{' '.join(cmd)} rc=0 but stdout is not a JWT: {preview!r}"
            )
        else:
            errors.append(
                f"{' '.join(cmd)} rc={result.returncode}: {result.stderr.strip()}"
            )
    raise RuntimeError("; ".join(errors) or "no command available")


def resolve_cloud_jwt(cloud_jwt: Optional[str] = None) -> str:
    """解析 Cloud JWT token：优先 AIME_USER_CLOUD_JWT 环境变量，其次命令行参数，
    再次 CLOUD_JWT 环境变量，最后尝试通过 AgentBuddy CLI 自动获取；全部失败才报错退出。"""
    aime_token = os.environ.get("AIME_USER_CLOUD_JWT", "").strip()
    if aime_token:
        return aime_token
    if cloud_jwt:
        return cloud_jwt
    env_token = os.environ.get("CLOUD_JWT")
    if env_token:
        return env_token
    try:
        return fetch_cloud_jwt()
    except Exception as e:
        print(
            "Error: 未获取到 Cloud JWT token。\n"
            "  自动获取失败: " + str(e) + "\n"
            "  可通过 --cloud-jwt 参数或 CLOUD_JWT 环境变量手动传入。",
            file=sys.stderr,
        )
        sys.exit(1)


def get_headers(jwt_token: str) -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Code-User-JWT": jwt_token,
    }


# ---------- HTTP ----------
def call_api(action: str, payload: Dict[str, Any], jwt_token: str) -> Dict[str, Any]:
    """向 Codebase OpenAPI 发起 POST 请求并返回 JSON 响应。"""
    url = f"{BASE_URL}?Action={action}"
    data = json.dumps(payload).encode("utf-8")
    headers = get_headers(jwt_token)
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"Error calling API {action}: HTTP {e.code}\n{body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error calling API {action}: {e.reason}", file=sys.stderr)
        sys.exit(1)


# ---------- Actions ----------
def get_repository(
    path: Optional[str] = None,
    repo_id: Optional[str] = None,
    with_permissions: bool = False,
    jwt_token: str = "",
) -> Dict[str, Any]:
    """获取仓库信息。至少传入 path 或 repo_id 之一。"""
    payload: Dict[str, Any] = {}
    if path:
        payload["Path"] = path
    if repo_id:
        payload["Id"] = repo_id
    if with_permissions:
        payload["WithPermissions"] = True

    if not payload:
        print("Error: Either path or repo_id must be provided.", file=sys.stderr)
        sys.exit(1)

    return call_api("GetRepository", payload, jwt_token)


def get_branch(repo_id: str, name: str, jwt_token: str = "") -> Dict[str, Any]:
    """获取分支信息。"""
    payload = {"RepoId": repo_id, "Name": name}
    return call_api("GetBranch", payload, jwt_token)


def get_merge_request(
    repo_id: str,
    number: Optional[int] = None,
    mr_id: Optional[str] = None,
    change_id: Optional[str] = None,
    with_commits: bool = False,
    with_versions: bool = False,
    jwt_token: str = "",
) -> Dict[str, Any]:
    """获取 Merge Request 详情。需提供 number / mr_id / change_id 之一。"""
    payload: Dict[str, Any] = {"RepoId": repo_id}
    if number is not None:
        payload["Number"] = number
    elif mr_id:
        payload["Id"] = mr_id
    elif change_id:
        payload["ChangeId"] = change_id
    else:
        print(
            "Error: Provide --number, --id, or --change-id.",
            file=sys.stderr,
        )
        sys.exit(1)

    if with_commits:
        payload["WithCommits"] = True

    if with_versions:
        payload["Selector"] = {"Version": True}

    return call_api("GetMergeRequest", payload, jwt_token)


def create_comment(
    repo_id: str,
    commentable_id: str,
    content: str,
    old_commit_id: str,
    new_commit_id: str,
    path: str,
    start_line: int,
    end_line: int,
    jwt_token: str = "",
) -> Dict[str, Any]:
    """在 MR 上创建行级评论。"""
    payload: Dict[str, Any] = {
        "CommentableType": "merge_request",
        "CommentableId": commentable_id,
        "RepoId": repo_id,
        "Content": content,
        "Position": {
            "Type": "content",
            "Side": "new",
            "OldCommitId": old_commit_id,
            "NewCommitId": new_commit_id,
            "Path": path,
            "StartLine": start_line,
            "StartColumn": 1,
            "EndLine": end_line,
            "EndColumn": 1000,
        },
    }
    return call_api("CreateComment", payload, jwt_token)


def parse_change_url(url: str) -> Tuple[int, int]:
    """从 bits devops change URL 中解析出 (dev_basic_id, change_id)。

    支持形如：
    - https://bits.bytedance.net/devops/<devops_id>/develop/detail/<dev_basic_id>/change/<change_id>
    - 带查询参数的同类链接
    """
    m = CHANGE_URL_RE.search(url)
    if not m:
        print(f"Error: 无法解析 bits change URL: {url}", file=sys.stderr)
        sys.exit(1)
    return int(m.group(1)), int(m.group(2))


def fetch_bits_change_mr_url(
    dev_basic_id: int, change_id: int, cloud_jwt: str
) -> str:
    """调 bits /api/v1/dev/task/changes?devBasicId=... 获取对应 change 的 MR URL。

    从 data.changeList 里按 change.id 精确匹配，返回
    change.manifest.codeElement.url（一条已支持解析的 bits/codebase MR URL）。
    """
    api_url = f"{BITS_BASE_URL}/api/v1/dev/task/changes?devBasicId={dev_basic_id}"
    headers = {
        "accept": "application/json, text/plain, */*",
        "x-jwt-token": cloud_jwt,
    }
    req = urllib.request.Request(api_url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        print(
            f"Error calling bits task/changes: HTTP {e.code}\n{detail}",
            file=sys.stderr,
        )
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error calling bits task/changes: {e.reason}", file=sys.stderr)
        sys.exit(1)

    change_list = (body.get("data") or {}).get("changeList") or []
    if not change_list:
        print(
            f"Error: bits devBasicId={dev_basic_id} 的 changeList 为空，"
            "请确认链接是否正确。",
            file=sys.stderr,
        )
        sys.exit(1)

    for item in change_list:
        change = item.get("change") or {}
        if change.get("id") == change_id:
            code_element = (change.get("manifest") or {}).get("codeElement") or {}
            mr_url = code_element.get("url")
            if not mr_url:
                print(
                    f"Error: change id={change_id} 缺少 codeElement.url，"
                    "无法推断 MR 链接。",
                    file=sys.stderr,
                )
                sys.exit(1)
            return mr_url

    available = ", ".join(str((c.get("change") or {}).get("id")) for c in change_list)
    print(
        f"Error: 在 devBasicId={dev_basic_id} 的 changeList 中未找到 "
        f"change id={change_id}（现有 change ids: {available}）。",
        file=sys.stderr,
    )
    sys.exit(1)


def parse_client_mr_url(url: str) -> int:
    """从 bits 客户端 MR URL 中解析出 Bits 客户端 MR ID。

    支持形如：
    - https://bits.bytedance.net/devops/1142536048898/code/detail/8376235?cr_tab=...
    - https://bits.bytedance.net/bytebus/devops/code/detail/8376235
    """
    m = CLIENT_MR_URL_RE.search(url)
    if not m:
        print(f"Error: 无法解析 bits 客户端 MR URL: {url}", file=sys.stderr)
        sys.exit(1)
    return int(m.group(1))


def parse_cr_tab(url: str) -> Optional[Dict[str, Any]]:
    """从 URL 的 cr_tab 参数解出 {"i": repo_id, "n": repo_path}。

    仅用于与 optimus 返回的 codebase_repo_id 做交叉校验，解不出返回 None 而非报错——
    用户只粘主路径（不带 cr_tab）是完全正常的用法。
    """
    try:
        query = urllib.parse.urlparse(url).query
        raw = urllib.parse.parse_qs(query).get("cr_tab", [None])[0]
        if not raw:
            return None
        padded = raw + "=" * (-len(raw) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        return decoded if isinstance(decoded, dict) else None
    except Exception:
        return None


def fetch_client_mr_context(client_mr_id: int, cloud_jwt: str) -> Dict[str, Any]:
    """调 optimus skill_action(get_single_mr) 获取客户端 MR 的 commit 指针等信息。

    返回响应中的 data 字典，含 merge_base_commit_id / last_commit_id（本函数强校验）
    以及 iid / codebase_repo_id（留给 create-comment 分支按需校验）。

    注意接口的三个反直觉之处，改动时勿"简化"：
    - 参数外层键是 data，用 params/arguments/input 均返回 400 "mr_id is required"；
    - 响应外层只有 message/code/data，没有 success 字段；
    - mr_id 无效时 HTTP 仍是 200，靠 body 里的 code(=400) 与 data(=null) 才能识别。
    """
    api_url = f"{OPTIMUS_BASE_URL}/api/v1/skill_action"
    payload = json.dumps({
        "action": "get_single_mr",
        "data": {"mr_id": client_mr_id},
    }).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "x-jwt-token": cloud_jwt,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        print(
            f"Error calling optimus get_single_mr: HTTP {e.code}\n{detail}",
            file=sys.stderr,
        )
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error calling optimus get_single_mr: {e.reason}", file=sys.stderr)
        sys.exit(1)

    mr = body.get("data")
    if body.get("code") != 200 or not isinstance(mr, dict):
        print(
            f"Error: 未获取到客户端 MR {client_mr_id} 的信息"
            f"（MR 不存在或当前账号无权限）。"
            f"上游返回 code={body.get('code')} message={body.get('message')!r}",
            file=sys.stderr,
        )
        sys.exit(1)

    missing = [k for k in ("merge_base_commit_id", "last_commit_id") if not mr.get(k)]
    if missing:
        print(
            f"Error: optimus 响应缺少 commit 字段: {missing}",
            file=sys.stderr,
        )
        sys.exit(1)
    return mr


def _warn_cr_tab_mismatch(url: str, mr: Dict[str, Any]) -> None:
    """cr_tab 里的 repo_id 与 optimus 返回不一致时打 warning，不作为失败条件。"""
    hint = parse_cr_tab(url)
    if hint and hint.get("i") and str(hint["i"]) != str(mr.get("codebase_repo_id")):
        print(
            f"Warning: cr_tab.i={hint['i']} 与 optimus 返回 "
            f"codebase_repo_id={mr.get('codebase_repo_id')} 不一致",
            file=sys.stderr,
        )


def parse_mr_url(url: str) -> Tuple[str, int]:
    """从 MR URL 中解析出 (repo_path, mr_number)。
    支持两种 URL 格式：
    - https://code.byted.org/pdi-qa/agent_report_service/merge_requests/513
    - https://bits.bytedance.net/code/ugc/Aweme/merge_requests/290510
    """
    m = re.search(r"code\.byted\.org/(.+)/merge_requests/(\d+)", url)
    if not m:
        m = re.search(r"bits\.bytedance\.net/code/(.+)/merge_requests/(\d+)", url)
    if not m:
        print(f"Error: 无法解析 MR URL: {url}", file=sys.stderr)
        sys.exit(1)
    return m.group(1), int(m.group(2))


def parse_mr_to_version(url: str) -> Optional[int]:
    """从 MR URL 的 query 中读取 to_version，未出现或空值等同未指定，返回 None。

    非整数值视为链接错误。
    """
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query, keep_blank_values=True)
    raw = query.get("to_version", [None])[-1]
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        print(f"Error: MR URL 参数 to_version={raw!r} 不是整数: {url}", file=sys.stderr)
        sys.exit(1)


def select_version_range(
    versions: List[Dict[str, Any]],
    to_version: Optional[int] = None,
) -> Dict[str, Any]:
    """按 to_version 从 MR Versions 中选出 diff 端点，缺省取最新版本。"""
    if not versions:
        print("Error: MR 未返回 Versions 数据", file=sys.stderr)
        sys.exit(1)
    by_number = {v.get("Number"): v for v in versions if isinstance(v.get("Number"), int)}
    if not by_number:
        print("Error: Versions 中缺少 Number 字段", file=sys.stderr)
        sys.exit(1)
    if to_version is None:
        to_version = max(by_number)
    if to_version not in by_number:
        available = ", ".join(str(n) for n in sorted(by_number))
        print(
            f"Error: MR 不存在版本 {to_version}（现有版本: {available}）。",
            file=sys.stderr,
        )
        sys.exit(1)

    to_v = by_number[to_version]
    from_commit = to_v.get("BaseCommitId", "")
    to_commit = to_v.get("SourceCommitId", "")
    if not from_commit or not to_commit:
        print("Error: Versions 中缺少 BaseCommitId 或 SourceCommitId", file=sys.stderr)
        sys.exit(1)

    return {
        "from_commit": from_commit,
        "to_commit": to_commit,
        "diff_range": f"{from_commit}...{to_commit}",
        "to_version": to_version,
    }


def resolve_mr_context(
    url: str,
    jwt_token: str,
    to_version: Optional[int] = None,
) -> Dict[str, Any]:
    """从 MR URL 解析出打评论 / 取 commit 范围所需的全部字段。

    返回 repo_id、mr_id（=commentable_id）、所选版本的 Base/Source commit
    （base_commit_id / source_commit_id，即评论 Position 的 Old/New）及 diff_range。
    版本优先取显式 to_version，其次取 URL query，都没有则为最新版本。
    复用给 get-mr-commits 和 create-comment --url 两个场景。
    """
    repo_path, mr_number = parse_mr_url(url)
    if to_version is None:
        to_version = parse_mr_to_version(url)
    repo_resp = get_repository(path=repo_path, jwt_token=jwt_token)
    repo_id = repo_resp.get("Result", {}).get("Repository", {}).get("Id")
    if not repo_id:
        print(f"Error: 无法从仓库路径 {repo_path} 获取 repo_id", file=sys.stderr)
        sys.exit(1)

    return _resolve_mr_context_by_ids(repo_id, mr_number, jwt_token, to_version)


def _resolve_mr_context_by_ids(
    repo_id: str,
    number: int,
    jwt_token: str,
    to_version: Optional[int] = None,
) -> Dict[str, Any]:
    """已知 codebase repo_id + MR Number 时，取 commentable_id 与所选版本的端点。"""
    mr_resp = get_merge_request(
        repo_id=repo_id, number=number, with_versions=True, jwt_token=jwt_token
    )
    mr = mr_resp.get("Result", {}).get("MergeRequest", {})
    mr_id = mr.get("Id", "")
    if not mr_id:
        print("Error: MR 响应缺少 Id（commentable_id）", file=sys.stderr)
        sys.exit(1)

    selection = select_version_range(mr.get("Versions", []), to_version)
    ctx: Dict[str, Any] = {
        "repo_id": repo_id,
        "mr_id": mr_id,
        "base_commit_id": selection["from_commit"],
        "source_commit_id": selection["to_commit"],
    }
    ctx.update(selection)
    return ctx


def resolve_client_mr_context(
    url: str, jwt_token: str, cloud_jwt_token: Optional[str] = None
) -> Dict[str, str]:
    """第 4 类（bits 客户端 MR）URL 的打评论上下文。

    optimus 只回 iid（codebase 侧 MR Number），行级评论需要 MergeRequest.Id，
    因此必须再走一次 codebase OpenAPI —— 此处对目标仓库的读权限是硬门槛。
    """
    cloud_jwt = resolve_cloud_jwt(cloud_jwt_token)
    client_mr_id = parse_client_mr_url(url)
    mr = fetch_client_mr_context(client_mr_id, cloud_jwt)
    _warn_cr_tab_mismatch(url, mr)

    missing = [k for k in ("iid", "codebase_repo_id") if not mr.get(k)]
    if missing:
        print(
            f"Error: optimus 响应缺少 {missing}，无法定位 codebase 侧 MR，"
            "该客户端 MR 暂无法留行级评论。",
            file=sys.stderr,
        )
        sys.exit(1)

    return _resolve_mr_context_by_ids(
        str(mr["codebase_repo_id"]), int(mr["iid"]), jwt_token
    )


def get_mr_commits(
    url: Optional[str] = None,
    repo_id: Optional[str] = None,
    number: Optional[int] = None,
    jwt_token: str = "",
    cloud_jwt_token: Optional[str] = None,
    to_version: Optional[int] = None,
) -> Dict[str, Any]:
    """返回 MR 所选版本的 diff 端点及可直接使用的 diff_range。

    版本选择规则见 select_version_range；显式 to_version 优先于 URL query。
    调用方应直接使用 diff_range，不得对端点取父提交或做偏移。

    url 支持以下四种形式，都走同一个入口（前两类可带 ?to_version=<N>）：
    - https://code.byted.org/<path>/merge_requests/<num>
    - https://bits.bytedance.net/code/<path>/merge_requests/<num>
    - https://bits.bytedance.net/devops/<ns>/develop/detail/<devBasicId>/change/<changeId>
      （先调 bits API 换出 codeElement.url，再走 MR URL 流程；需要 Cloud JWT）
    - https://bits.bytedance.net/devops/<space_id>/code/detail/<clientMrId>
      （bits 客户端 MR：调 optimus 直接取 commit 指针，不经 codebase OpenAPI；需要 Cloud JWT）

    也可不传 url，直接传 repo_id + number 直接查询。
    """
    if url:
        if CLIENT_MR_URL_RE.search(url):
            # 客户端 MR 由 optimus 直接给 merge_base / last commit，不在 Codebase Version 体系内。
            if to_version is not None or parse_mr_to_version(url) is not None:
                print(
                    "Error: bits 客户端 MR 不支持 to_version；"
                    "请改用 codebase MR 链接。",
                    file=sys.stderr,
                )
                sys.exit(1)
            cloud_jwt = resolve_cloud_jwt(cloud_jwt_token)
            client_mr_id = parse_client_mr_url(url)
            mr = fetch_client_mr_context(client_mr_id, cloud_jwt)
            _warn_cr_tab_mismatch(url, mr)
            return _mr_commits_result(
                mr["merge_base_commit_id"], mr["last_commit_id"]
            )
        if CHANGE_URL_RE.search(url):
            cloud_jwt = resolve_cloud_jwt(cloud_jwt_token)
            dev_basic_id, change_id = parse_change_url(url)
            url = fetch_bits_change_mr_url(dev_basic_id, change_id, cloud_jwt)
        ctx = resolve_mr_context(url, jwt_token, to_version)
        return {key: ctx[key] for key in _RESULT_KEYS}

    if not (repo_id and number is not None):
        print("Error: 需要传入 --url 或同时传入 --repo-id 和 --number", file=sys.stderr)
        sys.exit(1)

    mr_resp = get_merge_request(repo_id=repo_id, number=number, with_versions=True, jwt_token=jwt_token)
    versions = mr_resp.get("Result", {}).get("MergeRequest", {}).get("Versions", [])
    return select_version_range(versions, to_version)


_RESULT_KEYS = ("from_commit", "to_commit", "diff_range", "to_version")


def _mr_commits_result(
    from_commit: str,
    to_commit: str,
    to_version: Optional[int] = None,
) -> Dict[str, Any]:
    return {
        "from_commit": from_commit,
        "to_commit": to_commit,
        "diff_range": f"{from_commit}...{to_commit}",
        "to_version": to_version,
    }


# ---------- CLI ----------
def _build_parser() -> argparse.ArgumentParser:
    # 共享 parent：让 --codebase-jwt 在子命令前后都能识别，避免调用者拼错顺序。
    # 用 SUPPRESS 作默认值，避免子 parser 解析时用 None 覆盖顶层已设置的值。
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--codebase-jwt",
        default=argparse.SUPPRESS,
        help="Codebase JWT token（也可通过 CODEBASE_JWT 环境变量传入）",
    )
    common.add_argument(
        "--cloud-jwt",
        default=argparse.SUPPRESS,
        help="Cloud JWT token（也可通过 CLOUD_JWT 环境变量传入；bits change URL 与 bits 客户端 MR URL 需要）",
    )

    parser = argparse.ArgumentParser(
        description="Codebase OpenAPI CLI（仅标准库）",
        parents=[common],
    )
    sub = parser.add_subparsers(dest="command", help="可用子命令")

    # get-repository
    p_repo = sub.add_parser("get-repository", help="获取仓库信息", parents=[common])
    p_repo.add_argument("--path", help='仓库路径，例如 "byteapi/bytedcli"')
    p_repo.add_argument("--id", dest="repo_id", help="仓库 ID")
    p_repo.add_argument(
        "--with-permissions",
        action="store_true",
        help="是否返回权限信息",
    )

    # get-branch
    p_branch = sub.add_parser("get-branch", help="获取分支信息", parents=[common])
    p_branch.add_argument("--repo-id", required=True, help="仓库 ID")
    p_branch.add_argument("--name", required=True, help="分支名称")

    # get-mr
    p_mr = sub.add_parser("get-mr", help="获取 Merge Request 详情", parents=[common])
    p_mr.add_argument("--repo-id", required=True, help="仓库 ID")
    p_mr.add_argument("--number", type=int, help="MR 编号")
    p_mr.add_argument("--id", dest="mr_id", help="MR ID")
    p_mr.add_argument("--change-id", help="Change ID")
    p_mr.add_argument(
        "--with-commits",
        action="store_true",
        help="是否包含 commits 信息",
    )

    # get-mr-commits
    p_mr_commits = sub.add_parser("get-mr-commits", help="获取 MR 的 commit 范围", parents=[common])
    p_mr_commits.add_argument(
        "--url",
        help="MR 链接，例如 https://code.byted.org/org/repo/merge_requests/123；"
             "codebase MR 链接可带 ?to_version=<N>",
    )
    p_mr_commits.add_argument("--repo-id", help="仓库 ID（与 --number 配合使用）")
    p_mr_commits.add_argument("--number", type=int, help="MR 编号（与 --repo-id 配合使用）")
    p_mr_commits.add_argument(
        "--to-version", type=int, help="目标 Version.Number（默认最新版本），优先于 URL query"
    )

    # create-comment
    p_comment = sub.add_parser("create-comment", help="在 MR 上创建行级评论", parents=[common])
    p_comment.add_argument(
        "--url",
        help="MR 链接；传入后自动推断 --repo-id / --commentable-id / --old-commit-id / --new-commit-id"
             "（默认取最新 Version 的 Base/Source commit），显式传值可覆盖",
    )
    p_comment.add_argument("--repo-id", help="仓库 ID（不传 --url 时必填）")
    p_comment.add_argument("--commentable-id", help="MR ID（不传 --url 时必填）")
    p_comment.add_argument("--content", required=True, help="评论内容")
    p_comment.add_argument("--old-commit-id", help="Base commit ID（不传 --url 时必填）")
    p_comment.add_argument("--new-commit-id", help="Source commit ID（不传 --url 时必填）")
    p_comment.add_argument("--path", required=True, help="文件路径")
    p_comment.add_argument("--start-line", required=True, type=int, help="起始行号")
    p_comment.add_argument("--end-line", required=True, type=int, help="结束行号")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    jwt_token = resolve_jwt(getattr(args, "codebase_jwt", None))

    if args.command == "get-repository":
        result = get_repository(
            path=args.path,
            repo_id=args.repo_id,
            with_permissions=args.with_permissions,
            jwt_token=jwt_token,
        )
    elif args.command == "get-branch":
        result = get_branch(repo_id=args.repo_id, name=args.name, jwt_token=jwt_token)
    elif args.command == "get-mr":
        result = get_merge_request(
            repo_id=args.repo_id,
            number=args.number,
            mr_id=args.mr_id,
            change_id=args.change_id,
            with_commits=args.with_commits,
            jwt_token=jwt_token,
        )
    elif args.command == "get-mr-commits":
        result = get_mr_commits(
            url=args.url,
            repo_id=args.repo_id,
            number=args.number,
            jwt_token=jwt_token,
            cloud_jwt_token=getattr(args, "cloud_jwt", None),
            to_version=args.to_version,
        )
    elif args.command == "create-comment":
        repo_id = args.repo_id
        commentable_id = args.commentable_id
        old_commit_id = args.old_commit_id
        new_commit_id = args.new_commit_id
        if args.url:
            if CLIENT_MR_URL_RE.search(args.url):
                ctx = resolve_client_mr_context(
                    args.url, jwt_token, getattr(args, "cloud_jwt", None)
                )
            else:
                ctx = resolve_mr_context(args.url, jwt_token)
            repo_id = repo_id or ctx["repo_id"]
            commentable_id = commentable_id or ctx["mr_id"]
            old_commit_id = old_commit_id or ctx["base_commit_id"]
            new_commit_id = new_commit_id or ctx["source_commit_id"]
        missing = [
            name for name, value in (
                ("--repo-id", repo_id),
                ("--commentable-id", commentable_id),
                ("--old-commit-id", old_commit_id),
                ("--new-commit-id", new_commit_id),
            ) if not value
        ]
        if missing:
            print(
                f"Error: 缺少参数 {', '.join(missing)}；请通过 --url 自动推断或显式传入。",
                file=sys.stderr,
            )
            sys.exit(1)
        result = create_comment(
            repo_id=repo_id,
            commentable_id=commentable_id,
            content=args.content,
            old_commit_id=old_commit_id,
            new_commit_id=new_commit_id,
            path=args.path,
            start_line=args.start_line,
            end_line=args.end_line,
            jwt_token=jwt_token,
        )
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

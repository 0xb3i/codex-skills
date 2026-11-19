#!/usr/bin/env python3
"""Prepare and inspect opt-in skill evaluations; never starts a model."""

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import unicodedata

try:
    import yaml
except ImportError as exc:
    raise SystemExit("缺少依赖：请在所用 Python 环境安装 PyYAML。") from exc


EXCLUDED = {"evals", "__pycache__", ".git", ".cache", "cache", ".pytest_cache"}
EXCLUDED_FILES = {"assessment.json", "improvement-candidates.md", ".DS_Store"}
NAME = re.compile(r"^[a-z0-9]+(?:[-:][a-z0-9]+)*$")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON 字段重复：{key}")
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicate_keys)


def fields(value, required, label):
    if not isinstance(value, dict) or set(value) != set(required):
        raise ValueError(f"{label} 字段必须恰为：{', '.join(required)}")


def string(value, label, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{label} 必须是{'可为空' if allow_empty else '非空'}字符串")


def strings(value, label, nonempty=False):
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{label} 必须是{'非空' if nonempty else ''}字符串数组")
    for item in value:
        string(item, label)
    if len(value) != len(set(value)):
        raise ValueError(f"{label} 有重复项")


def relative_path(value):
    string(value, "workspace 路径")
    path = PurePosixPath(value)
    if (path.is_absolute() or any(part in ("", ".", "..") for part in value.split("/"))
            or "\\" in value or ":" in value or any(ord(char) < 32 for char in value)
            or path.as_posix() != value):
        raise ValueError(f"不安全的 workspace 相对路径：{value!r}")
    return value


def validate_paths(paths, label):
    normalized = set()
    for value in paths:
        relative_path(value)
        identity = unicodedata.normalize("NFC", value).casefold()
        if identity in normalized:
            raise ValueError(f"{label} 存在大小写或 Unicode 路径冲突：{value}")
        normalized.add(identity)
    for value in normalized:
        if any(parent.as_posix() in normalized for parent in PurePosixPath(value).parents):
            raise ValueError(f"{label} 文件与父目录冲突：{value}")


def load_suite(path):
    suite = read_json(path)
    fields(suite, ("skill", "cases"), "suite")
    string(suite["skill"], "skill")
    if not NAME.fullmatch(suite["skill"]):
        raise ValueError("skill 名称格式不正确")
    if not isinstance(suite["cases"], list) or not suite["cases"]:
        raise ValueError("cases 必须是非空数组")
    ids = set()
    for case in suite["cases"]:
        fields(case, ("id", "origin", "prompt", "context", "fixtures", "expected"), "case")
        string(case["id"], "case.id")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", case["id"]):
            raise ValueError(f"case.id 格式不正确：{case['id']}")
        if case["id"] in ids:
            raise ValueError(f"重复 case.id：{case['id']}")
        ids.add(case["id"])
        fields(case["origin"], ("kind", "note"), "origin")
        if case["origin"]["kind"] not in ("user_feedback", "constructed"):
            raise ValueError(f"{case['id']} 的 origin.kind 不受支持")
        string(case["origin"]["note"], "origin.note")
        string(case["prompt"], "prompt")
        string(case["context"], "context", allow_empty=True)
        if not isinstance(case["fixtures"], dict):
            raise ValueError("fixtures 必须是相对路径到文本的映射")
        validate_paths(case["fixtures"], "fixtures")
        for content in case["fixtures"].values():
            string(content, "fixture 内容", allow_empty=True)
        expected = case["expected"]
        fields(expected, ("trigger", "changed_files", "criteria"), "expected")
        fields(expected["trigger"], ("required", "optional", "forbidden"), "expected.trigger")
        seen = set()
        for kind, names in expected["trigger"].items():
            strings(names, f"trigger.{kind}")
            if any(not NAME.fullmatch(name) for name in names):
                raise ValueError(f"trigger.{kind} 有无效技能名")
            if seen.intersection(names):
                raise ValueError(f"{case['id']} 的 trigger 集合不互斥")
            seen.update(names)
        strings(expected["changed_files"], "changed_files")
        validate_paths(expected["changed_files"], "changed_files")
        strings(expected["criteria"], "criteria", nonempty=True)
    return suite


def tree(root, exclude_evals=False):
    """Hash files without following links; include directories to detect scope changes."""
    result = {}
    if not root.is_dir() or root.is_symlink():
        return result
    for current, directories, files in os.walk(root, followlinks=False):
        for name in sorted(directories + files):
            path = Path(current) / name
            if exclude_evals and (name in EXCLUDED or name in EXCLUDED_FILES or name.endswith((".pyc", ".pyo"))):
                if name in directories:
                    directories.remove(name)
                continue
            key = path.relative_to(root).as_posix()
            if path.is_symlink():
                result[key] = {"kind": "symlink", "target": os.readlink(path)}
            elif path.is_dir():
                result[key] = {"kind": "directory"}
            elif path.is_file():
                result[key] = {"kind": "file", "sha256": sha256(path.read_bytes())}
            else:
                raise ValueError(f"不支持的特殊文件：{path}")
    return result


def skill_info(path):
    text = (path / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.DOTALL)
    if not match:
        raise ValueError(f"缺少技能 frontmatter：{path}")
    metadata = yaml.safe_load(match.group(1))
    if not isinstance(metadata, dict):
        raise ValueError(f"无效技能 frontmatter：{path}")
    for field in ("name", "description"):
        string(metadata.get(field), f"{path} 的 {field}")
    if not NAME.fullmatch(metadata["name"]):
        raise ValueError(f"无效技能名：{metadata['name']}")
    return {field: metadata[field] for field in ("name", "description")}


def is_within(path, parent):
    return path == parent or parent in path.parents


def prepare(args):
    suite_path = args.suite.expanduser().resolve()
    suite = load_suite(suite_path)
    case = next((case for case in suite["cases"] if case["id"] == args.case_id), None)
    if case is None:
        raise ValueError(f"未找到案例：{args.case_id}")
    output = args.output.expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise ValueError(f"output 已存在，不覆盖：{output}")
    catalog, sources = [], []
    for source in args.skill_dir:
        source = source.expanduser().resolve()
        if is_within(output.resolve(), source):
            raise ValueError("output 不得位于源技能目录内")
        info = skill_info(source)
        if info["name"] in {item["name"] for item in catalog}:
            raise ValueError(f"重复候选技能：{info['name']}")
        manifest = tree(source, exclude_evals=True)
        if any(item["kind"] == "symlink" for item in manifest.values()):
            raise ValueError(f"技能快照包含软链接，请先提供完整本地目录：{source}")
        catalog.append(info)
        sources.append({"name": info["name"], "path": str(source), "files": manifest,
                        "sha256": sha256(json_bytes(manifest))})
    names = {item["name"] for item in catalog}
    oracle_names = {name for group in case["expected"]["trigger"].values() for name in group}
    if not oracle_names.issubset(names) or suite["skill"] not in names:
        raise ValueError("--skill-dir 必须覆盖 suite.skill 和本题 trigger oracle 中的全部技能")
    output.mkdir()
    try:
        subject = output / "subject"
        subject.mkdir()
        (subject / "request.json").write_bytes(json_bytes({key: case[key] for key in ("prompt", "context")}))
        (subject / "catalog.json").write_bytes(json_bytes(catalog))
        common = (
            "本轮仅可读取本 subject 目录中的资料。request.json 是原始用户请求与上下文。\n"
            "不可访问上级目录中的 assessment.json、原始题库或真实技能源目录，不调用外部服务。\n"
            "原生智能体共享文件系统；这里仅作流程隔离，不是强安全沙箱。\n"
        )
        if args.stage == "trigger":
            instruction = common + (
                "根据原始请求和 catalog.json 中的 name/description 判断要使用的技能。\n"
                "不要加载技能正文或执行任务。只新建 selection.json，格式为 "
                '{"selected": ["技能名"], "reason": "简短理由"}，无需触发时 selected 为空数组。\n'
            )
        else:
            workspace = subject / "workspace"
            workspace.mkdir()
            for relative, content in case["fixtures"].items():
                destination = workspace / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(content, encoding="utf-8")
            for source in sources:
                snapshot = subject / "skills" / source["name"]
                snapshot.mkdir(parents=True)
                for relative, entry in source["files"].items():
                    destination = snapshot / relative
                    if entry["kind"] == "directory":
                        destination.mkdir(parents=True, exist_ok=True)
                    else:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(Path(source["path"]) / relative, destination)
            validator = Path(__file__).resolve().parents[2] / ".system/skill-creator/scripts/quick_validate.py"
            if validator.is_file():
                (subject / "tools").mkdir()
                shutil.copyfile(validator, subject / "tools/quick_validate.py")
                validation_note = "需要技能结构校验时，使用 python3 tools/quick_validate.py workspace/目标技能目录。\n"
            else:
                validation_note = "本目录未提供技能结构校验器；如需校验请如实记录未运行，不到真实环境补找。\n"
            instruction = common + (
                "根据原始请求选择并读取 skills/ 下适用的技能快照，在 workspace/ 内完成任务。\n"
                "workspace/ 中的文件对应题设环境；所有业务修改仅允许落在 workspace/。\n"
                "workspace/skills/ 是题设中的可修改对象，skills/ 是只读操作依据，两者不可混淆。\n"
                "workspace/ 中的案例文件若为题设目标，可以按请求维护；它们不属于上级受保护题库。\n"
                "不得修改技能快照、题面或其他输入文件；另将最终答复写入本目录的 response.md。\n"
                "技能中的外部路径、工具和真实副作用不得在本次演练访问或执行；资料不足时如实说明。\n"
            ) + validation_note
        (subject / "instructions.md").write_text(instruction, encoding="utf-8")
        for source in sources:
            if tree(Path(source["path"]), exclude_evals=True) != source["files"]:
                raise ValueError(f"准备期间源技能发生变化，请重新准备：{source['name']}")
        assessment = {"schema_version": 1, "stage": args.stage, "case_id": case["id"],
                      "suite": str(suite_path), "suite_sha256": sha256(suite_path.read_bytes()),
                      "case_sha256": sha256(json_bytes(case)), "expected": case["expected"],
                      "fixtures": case["fixtures"], "sources": sources, "subject_files": tree(subject)}
        (output / "assessment.json").write_bytes(json_bytes(assessment))
    except Exception:
        shutil.rmtree(output)
        raise
    return {"subject": str(subject), "assessment": str(output / "assessment.json"),
            "stage": args.stage, "model_started": False}


def changes(before, after):
    return {path: {"before": before.get(path), "after": after.get(path)}
            for path in sorted(set(before) | set(after)) if before.get(path) != after.get(path)}


def file_changes(delta):
    return {path: change for path, change in delta.items()
            if any(entry and entry["kind"] != "directory" for entry in change.values())}


def inspect(args):
    output = args.output.expanduser().resolve()
    assessment = read_json(output / "assessment.json")
    if assessment.get("schema_version") != 1 or assessment.get("stage") not in ("trigger", "execution"):
        raise ValueError("无法识别 assessment 格式或 stage")
    subject = output / "subject"
    after = tree(subject)
    delta = changes(assessment["subject_files"], after)
    stage = assessment["stage"]
    allowed_response = "selection.json" if stage == "trigger" else "response.md"
    outside = {path: change for path, change in delta.items()
               if path != allowed_response and not (stage == "execution" and (path == "workspace" or path.startswith("workspace/")))}
    root_extras = sorted(path.name for path in output.iterdir() if path.name not in ("subject", "assessment.json"))
    if not subject.is_dir() or subject.is_symlink():
        outside["."] = {"error": "subject 已删除或替换为非普通目录"}
    source_changes = {}
    for source in assessment["sources"]:
        delta_source = changes(source["files"], tree(Path(source["path"]), exclude_evals=True))
        if delta_source:
            source_changes[source["name"]] = delta_source
    result = {"stage": stage, "case_id": assessment["case_id"],
              "case_sha256": assessment["case_sha256"], "suite_sha256": assessment["suite_sha256"],
              "skill_hashes": {source["name"]: source["sha256"] for source in assessment["sources"]},
              "protected_changes": outside, "output_extras": root_extras, "source_changes": source_changes,
              "scope_note": "仅比较 subject、output 直接子项和已登记源技能；不监控共享文件系统其他位置，也不防篡改。"}
    scope_ok = not (outside or root_extras or source_changes)
    if "." in outside:
        result.update(deterministic_pass=False, evaluation_pass=None, semantic_status="not_judged")
        return result
    if stage == "trigger":
        selection_path = subject / "selection.json"
        try:
            if not selection_path.is_file() or selection_path.is_symlink():
                raise ValueError("缺少普通文件 selection.json")
            selection = read_json(selection_path)
            fields(selection, ("selected", "reason"), "selection")
            strings(selection["selected"], "selected")
            string(selection["reason"], "reason")
            selected = set(selection["selected"])
            oracle = assessment["expected"]["trigger"]
            known = {source["name"] for source in assessment["sources"]}
            result["selection"] = selection
            result["missing_required"] = sorted(set(oracle["required"]) - selected)
            result["selected_forbidden"] = sorted(set(oracle["forbidden"]) & selected)
            result["unknown_selected"] = sorted(selected - known)
            result["unscored_selected"] = sorted(selected - set().union(*map(set, oracle.values())))
            result["deterministic_pass"] = scope_ok and not any(result[key] for key in (
                "missing_required", "selected_forbidden", "unknown_selected"))
        except (OSError, ValueError) as exc:
            result.update(selection_error=str(exc), deterministic_pass=False)
    else:
        delta_workspace = {path[len("workspace/"):]: change for path, change in file_changes(delta).items()
                           if path.startswith("workspace/")}
        expected = set(assessment["expected"]["changed_files"])
        actual = set(delta_workspace)
        diffs = {}
        for path, change in delta_workspace.items():
            old = assessment["fixtures"].get(path, "")
            if change["after"] and change["after"]["kind"] == "file":
                try:
                    new = (subject / "workspace" / path).read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    diffs[path] = "二进制变更；见哈希。"
                    continue
            elif change["after"] is None:
                new = ""
            else:
                diffs[path] = "目标变为非普通文件；见变更记录。"
                continue
            diffs[path] = "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                                     fromfile="before/" + path, tofile="after/" + path))
        response = subject / "response.md"
        response_present = response.is_file() and not response.is_symlink() and bool(response.read_bytes().strip())
        unsafe_workspace = sorted(path for path, entry in after.items()
                                  if (path == "workspace" or path.startswith("workspace/")) and entry["kind"] == "symlink")
        result.update(changed_files=sorted(actual), changes=delta_workspace, diffs=diffs,
                      missing_expected=sorted(expected - actual), unexpected_changed=sorted(actual - expected),
                      response_present=response_present, unsafe_workspace=unsafe_workspace,
                      criteria=assessment["expected"]["criteria"], semantic_status="not_judged")
        result["deterministic_pass"] = scope_ok and actual == expected and response_present and not unsafe_workspace
    result["evaluation_pass"] = None
    result["note"] = "确定性检查不等于模型行为或语义评测通过；语义及最终结论由独立裁判判断。"
    return result


def main():
    parser = argparse.ArgumentParser(description="按明确请求准备技能评测与确定性检查；不启动模型、不定时运行。")
    commands = parser.add_subparsers(dest="command", required=True)
    validate_parser = commands.add_parser("validate", help="校验案例 schema、路径和 oracle")
    validate_parser.add_argument("suite", type=Path, nargs="+")
    prepare_parser = commands.add_parser("prepare", help="创建不含答案的受试目录和独立裁判资料")
    prepare_parser.add_argument("suite", type=Path)
    prepare_parser.add_argument("case_id")
    prepare_parser.add_argument("--stage", choices=("trigger", "execution"), required=True)
    prepare_parser.add_argument("--skill-dir", type=Path, action="append", required=True)
    prepare_parser.add_argument("--output", type=Path, required=True, help="父目录存在，目标目录尚不存在")
    inspect_parser = commands.add_parser("inspect", help="检查选择、真实文件变化和保护范围；语义留给裁判")
    inspect_parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            seen, count = set(), 0
            for path in args.suite:
                suite = load_suite(path.expanduser())
                for case in suite["cases"]:
                    identity = (suite["skill"], case["id"])
                    if identity in seen:
                        raise ValueError(f"重复案例：{identity[0]}/{identity[1]}")
                    seen.add(identity)
                    count += 1
            result = {"suites": len(args.suite), "cases": count, "valid": True, "model_started": False}
        elif args.command == "prepare":
            result = prepare(args)
        else:
            result = inspect(args)
        print(json_bytes(result).decode("utf-8"), end="")
        return 1 if result.get("deterministic_pass") is False else 0
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"检查失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""校验代码大师审查模式的最终缺陷产物。

本脚本只做产物闸门，不生成缺陷、不把缺失文件兜底为空数组。
如果 final_comments.json 不存在，说明评审流程未完成，必须返回非 0。
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = ("title", "file", "start_line", "end_line", "severity", "category", "confidence", "rationale")
VALID_SEVERITIES = {"P0", "P1", "P2"}


def fail(message: str) -> int:
    print(f"[final-comments] {message}", file=sys.stderr)
    return 1


def validate_defect(defect: Any, index: int) -> str:
    if not isinstance(defect, dict):
        return f"defect #{index} must be a JSON object"

    for field in REQUIRED_FIELDS:
        if field not in defect:
            return f"defect #{index} missing required field: {field}"

    for field in ("title", "file", "severity", "category", "rationale"):
        value = defect.get(field)
        if not isinstance(value, str) or not value.strip():
            return f"defect #{index} field {field} must be a non-empty string"

    if defect.get("severity") not in VALID_SEVERITIES:
        return f"defect #{index} severity must be one of {sorted(VALID_SEVERITIES)}"

    for field in ("start_line", "end_line"):
        value = defect.get(field)
        if not isinstance(value, int) or value < 1:
            return f"defect #{index} field {field} must be a positive integer"

    confidence = defect.get("confidence")
    if not isinstance(confidence, int) or confidence < 1 or confidence > 10:
        return f"defect #{index} confidence must be an integer in [1, 10]"

    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 final_comments.json 是否存在且结构合法")
    parser.add_argument("final_comments", help="final_comments.json 路径")
    args = parser.parse_args()

    path = Path(args.final_comments)
    if not path.is_file():
        return fail(f"missing final_comments.json: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return fail(f"invalid JSON in {path}: {exc}")

    if not isinstance(data, list):
        return fail("final_comments.json must be a JSON array")

    for index, defect in enumerate(data, start=1):
        error = validate_defect(defect, index)
        if error:
            return fail(error)

    print(f"[final-comments] valid final_comments.json: {path}, defects={len(data)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

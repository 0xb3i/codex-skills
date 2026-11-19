#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


SKIP_DIRS = {
    '.git', '.svn', '.hg', '.idea', '.vscode', '__pycache__', 'node_modules',
    '.cache', '.pytest_cache', '.mypy_cache', '__MACOSX', '_organized', '_trash_review',
}
GENERIC_DIRS = {
    'data', 'docs', 'doc', 'files', 'file', 'new folder', 'untitled folder', 'misc',
    'other', 'others', 'tmp', 'temp', 'test', 'tests', 'archive', 'backup', 'bak', 'deep', 'nested',
    '资料', '文件', '文档', '数据', '其他', '杂项', '临时', '测试', '备份',
}
STOPWORDS = {
    'final', 'copy', '副本', '版本', '新建', 'untitled', 'file', 'data', 'doc',
    'document', 'report', 'result', 'results', 'v', 'ver', 'version', 'the', 'and',
}
REVIEW_EXTS = {'.tmp', '.temp', '.bak', '.old', '.orig', '.swp', '.pyc'}
REVIEW_NAMES = {'.ds_store', 'thumbs.db', 'desktop.ini'}


def slug(text, fallback='misc'):
    text = re.sub(r'[_\s]+', '-', text.strip().lower())
    text = re.sub(r'[^\w\-\u4e00-\u9fff]+', '-', text)
    text = re.sub(r'-{2,}', '-', text).strip('-_')
    return text or fallback


def tokens(text):
    raw = re.split(r'[^\w\u4e00-\u9fff]+', text.lower())
    out = []
    for token in raw:
        if not token or token in STOPWORDS:
            continue
        if re.fullmatch(r'\d{1,2}|20\d{2}|v\d+', token):
            continue
        out.append(token)
    return out


def review_reason(path):
    name = path.name.lower()
    if name in REVIEW_NAMES or name.startswith('~$'):
        return 'review-temp-name'
    if path.suffix.lower() in REVIEW_EXTS:
        return 'review-temp-extension'
    return None


def group_for(path, root):
    rel = path.relative_to(root)
    parents = [p for p in rel.parts[:-1] if slug(p) not in GENERIC_DIRS]
    if parents:
        return slug(parents[-1])
    stem_tokens = tokens(path.stem)
    if len(stem_tokens) >= 2:
        return slug('-'.join(stem_tokens[:2]))
    if stem_tokens:
        return slug(stem_tokens[0])
    return slug(path.suffix.lstrip('.') or 'misc')


def short_name(path, group, used):
    stem_tokens = [t for t in tokens(path.stem) if t not in set(group.split('-'))]
    stem = slug('-'.join(stem_tokens[:3]), 'file')
    candidate = f'{stem}{path.suffix.lower()}'
    if candidate not in used:
        used.add(candidate)
        return candidate
    i = 2
    while f'{stem}-{i}{path.suffix.lower()}' in used:
        i += 1
    candidate = f'{stem}-{i}{path.suffix.lower()}'
    used.add(candidate)
    return candidate


def flat_name(path, group, used):
    stem = slug(path.stem, group)
    candidate = f'{stem}{path.suffix.lower()}'
    if candidate in used:
        candidate = f'{group}-{stem}{path.suffix.lower()}'
    if candidate not in used:
        used.add(candidate)
        return candidate
    i = 2
    while f'{group}-{stem}-{i}{path.suffix.lower()}' in used:
        i += 1
    candidate = f'{group}-{stem}-{i}{path.suffix.lower()}'
    used.add(candidate)
    return candidate


def iter_files(root, target_root):
    for path in root.rglob('*'):
        if not path.is_file():
            continue
        rel_parts = set(path.relative_to(root).parts[:-1])
        if rel_parts & SKIP_DIRS:
            continue
        if target_root in path.parents:
            continue
        yield path


def build_plan(root, target_root):
    moves, cleanup_candidates, grouped = [], [], {}
    for path in sorted(iter_files(root, target_root)):
        reason = review_reason(path)
        if reason:
            cleanup_candidates.append({'path': str(path), 'reason': reason})
            continue
        group = group_for(path, root)
        grouped.setdefault(group, []).append(path)
    used_at_root = {path.name for path in target_root.iterdir()} if target_root.exists() else set()
    for group, paths in sorted(grouped.items()):
        if len(paths) == 1:
            path = paths[0]
            name = flat_name(path, group, used_at_root)
            moves.append({'source': str(path), 'target': str(target_root / name), 'group': group})
            continue
        group_root = target_root / group
        used = {path.name for path in group_root.iterdir()} if group_root.exists() else set()
        for path in paths:
            name = short_name(path, group, used)
            moves.append({'source': str(path), 'target': str(target_root / group / name), 'group': group})
    return {'root': str(root), 'target_root': str(target_root), 'moves': moves,
            'cleanup_candidates': cleanup_candidates}


def main():
    parser = argparse.ArgumentParser(description='Draft a shallow folder organization plan without moving or deleting source files.')
    parser.add_argument('folder')
    parser.add_argument('--target-root')
    parser.add_argument('--out', default='organize_plan.json')
    args = parser.parse_args()

    root = Path(args.folder).expanduser().resolve()
    if not root.is_dir():
        parser.error('folder must be an existing directory')
    output = Path(args.out).expanduser().resolve()
    if output.is_relative_to(root):
        parser.error('--out must be outside the scanned folder')
    target_root = Path(args.target_root).expanduser().resolve() if args.target_root else root / '_organized'
    plan = build_plan(root, target_root)
    with output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(plan, ensure_ascii=False, indent=2))
    print(f"moves={len(plan['moves'])} cleanup_candidates={len(plan['cleanup_candidates'])} plan={args.out}")


if __name__ == '__main__':
    main()

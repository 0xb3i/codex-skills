---
name: data-organizer
description: "Use when Codex needs to improve the findability of a cluttered folder or data workspace: organize, archive, rename, group related artifacts, flatten overly deep paths, split crowded flat folders into shallow topic folders, merge scattered review/index artifacts, or clean temporary/obsolete files. Trigger proactively when file discovery degrades, such as many sibling files with shared meaning, inconsistent naming, duplicate derived outputs, or review artifacts that should be compared together."
---

# Data Organizer

## 核心原则

以用户查找方便为第一目标：先看文件应该如何被人找回，再决定目录和文件名。默认保持浅层结构：`主题文件夹/文件`；如果目标根目录本身已经是主题目录，直接使用 `文件`，不要再套同义父目录或子目录。最多只在确有必要时增加第二层。

## 工作流

1. 递归扫描目标目录，排除 `.git`、`node_modules`、`__pycache__`、系统缓存和已生成的整理目录。
2. 先生成整理计划，不直接动文件。可用 `scripts/organize_files.py <folder> --out plan.json` 做初扫。
3. 按主题归组，而不是只按扩展名归档。优先使用：项目名、客户/对象名、日期批次、数据集名、报告主题、共同文件名前缀。
4. 压平目录：目标路径优先为 `<目标根>/<主题>/<简洁文件名.ext>`；若 `<目标根>` 已经清楚表达主题，则用 `<目标根>/<简洁文件名.ext>`。避免把旧目录结构原样搬过去，也不要创建同义套娃目录；但单目录里如果堆了十几个以上共享长前缀的文件，不要为了“扁平”全塞一层，应拆成 `<目标根>/<主题>/<子主题>/<短文件名.ext>`。
5. 简化文件名：去掉无意义词、重复目录名、`final_final`、副本标记、过长日期串；优先用目录名承载共同前缀（如 `planner_eval_1000`、`product_analysis`、`ai_search`），文件名只保留同目录内区分所需的关键词、版本、日期、语言、格式。
6. 审阅产物优先合并：同一对象的多个 review HTML、报告、截图索引或 demo 说明，如果用户通常会横向比较，优先合成一个总览文件（如 `name.tracks.review.html`），保留原始训练/数据文件，删除或替换分散的派生审阅文件。
7. 清理废文件：删除高置信临时/缓存/备份文件；对不确定的“old/废弃/test/测试”文件先列入计划，只有能从内容或同目录上下文确认无用时再删除。Codex 本轮刚生成且已被合并替代的临时/demo/review 派生文件可直接清理。
8. 执行后做一次复扫，确认没有空目录、重复目标名、过深路径和明显遗漏。若目标目录顶层仍有一串同主题 sibling 文件、共享长前缀文件、重复派生产物或应一起审阅的报告/索引文件，判定整理未完成，继续归入主题目录并缩短文件名，直到顶层只剩少量主题目录或真正独立文件。

## 判断归属

- 同一项目的原始数据、处理脚本、结果表、说明文档放同一主题目录。
- 同一对象的不同格式版本放一起，例如 `csv/xlsx/pdf/png`。
- 同一时间批次但主题不同，不强行合并；日期只作为辅助标识。
- 不要创建 `图片/文档/表格` 这种纯类型目录，除非用户明确只按文件类型找。
- 对混乱目录，先用文件名和父目录名归组；必要时抽样读取文件头或元数据确认。

## 命名规则

- 目录名：短主题名，2-5 个词为宜，如 `seed-review`、`audience-profiles`、`2026-06-eval`。
- 文件名：只保留同目录内区分所需信息，如 `summary.csv`、`raw.xlsx`、`review-notes.md`、`v2-results.json`。
- 同名冲突时追加最小区分词，不追加长哈希；仍冲突再用 `-2`、`-3`。
- 保留扩展名原样；不要为“看起来统一”而转换格式。

## 删除口径

可直接删除：`.DS_Store`、`Thumbs.db`、`*.tmp`、`*.temp`、`*.bak`、`*.old`、`*.orig`、`*.swp`、`*.pyc`、`~$*`、空目录、明显缓存目录。

谨慎删除：名称含 `test`、`测试`、`草稿`、`draft`、`old`、`废弃`、`deprecated` 的真实数据文件。先确认它不是唯一版本、不是训练/评估所需样本、不是用户可追溯的来源文件。

## 工具脚本

`scripts/organize_files.py` 用于生成和执行初步整理计划：

```bash
python3 scripts/organize_files.py /path/to/folder --out plan.json
python3 scripts/organize_files.py /path/to/folder --apply --delete-cleanup
```

默认只写计划；`--apply` 才移动文件，`--delete-cleanup` 才删除高置信清理项。脚本是第一轮机械整理工具，执行前仍要按本 Skill 的归组原则快速审查计划。

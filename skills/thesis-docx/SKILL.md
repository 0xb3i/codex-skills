---
name: thesis-docx
description: 当任务需要从 0 或者从已有 markdown 生成 docx 文档时使用。
---

# Thesis Docx

## 概述

这个 skill 提供了生成 Word 的全流程。正文维护在 Markdown，封面与摘要维护在 metadata JSON，参考文献维护在 BibTeX，最后由 `scripts/thesis_docx.py` 按 profile 生成最终 DOCX。

## 工作流

1. 在 Markdown 中写正文，并用 citekey，例如 `[@chen2024bge]`
2. 在 `.bib` 中维护参考文献
3. 在 metadata JSON 中维护封面、摘要、关键词
4. 运行 `scripts/thesis_docx.py build ...`
5. 运行 `scripts/export-docx-pdf.sh ...` 自动导出 PDF
6. 在 Word 或 WPS 中更新一次字段

## 固定分支

1. `build --markdown ...`
   生成 DOCX。缺 `metadata` 时自动补占位 metadata；缺 `bib` 时若正文中有 citekey，会自动补占位 BibTeX。

2. `build` 不传 `--markdown`
   生成空白 DOCX。

3. `restyle --input ...`
   只对已有 DOCX 做格式统一，不负责生成封面、摘要、目录等前置部分。

## 常用命令

在项目虚拟环境中安装依赖：

```bash
uv pip install python-docx --python .venv/bin/python
.venv/bin/python -c "import docx"
```

skill 路径：

```bash
if [ -d codex-skills/thesis-docx ]; then
  SKILL_DIR="codex-skills/thesis-docx"
else
  SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/thesis-docx"
fi
```

从源文件生成课程论文 DOCX：

```bash
.venv/bin/python "$SKILL_DIR/scripts/thesis_docx.py" build \
  --metadata report/metadata.json \
  --markdown report/manuscript.md \
  --bib report/references.bib \
  --spec "$SKILL_DIR/assets/profiles/course-paper.json" \
  --no-toc \
  --output report/report.docx
```

将 DOCX 自动导出为 PDF：

```bash
zsh "$SKILL_DIR/scripts/export-docx-pdf.sh" report/report.docx report/report.pdf
```

用同一个 profile 重排已有 DOCX：

```bash
.venv/bin/python "$SKILL_DIR/scripts/thesis_docx.py" restyle \
  --input draft.docx \
  --spec "$SKILL_DIR/assets/profiles/course-paper.json" \
  --output output/doc/restyled.docx
```

## 参考说明

- 修改整体构建流程前，先看 `references/workflow.md`

## 资源结构

- `assets/profiles/course-paper.json`
  课程论文 profile，控制页边距、字体、目录样式、封面、页眉页脚和参考文献样式
- `assets/references.template.bib`
  最小 BibTeX 示例
- `assets/templates/metadata.json`
  metadata 示例
- `assets/templates/manuscript.md`
  Markdown 正文示例
- `assets/csl/china-national-standard-gb-t-7714-2015-numeric.csl`
  引用样式文件
- `scripts/thesis_docx.py`
  构建和重排 DOCX 的核心脚本
- `scripts/export-docx-pdf.sh`
  将生成好的 DOCX 自动导出为 PDF，优先使用 LibreOffice，若不可用则回退到 macOS 的 Word 自动化

## Markdown 写作规范

### 1. 标题

- 只写纯标题，不要手工写封面、目录、页码。
- 一级标题用 `# 标题`
- 二级标题用 `## 标题`
- 三级标题用 `### 标题`
- 不要手工写“一、二、三”或“1.1、1.2”，由 skill 统一生成。

### 2. 文献引用

- 正文中统一使用 citekey，例如 `[@chen2024bge]`
- 不要手写 `[1]`、`[2]`
- 不要在 `manuscript.md` 末尾手写参考文献列表
- 所有文献都放在 `report/references.bib`

### 3. 图片

- 图片文件放在 `report/figures/`
- Markdown 图片写法示例：

```md
[[fig:system_funnel]]

![图 2 系统漏斗式架构图。](figures/02_system_funnel.png){ width=95% }
```

- 规则：
  - 标签行必须单独一行，格式是 `[[fig:唯一标识]]`
  - 标签行后必须空一行，再写图片语法
  - 图片题注必须单独写在图片语法里
  - 题注文本必须以 `图 N ...` 开头
  - 不要把图片说明写成长段落混在正文里

### 4. 表格

- 表题必须单独一行，放在表格前面
- 表格示例：

```md
[[tbl:core_results]]

表 1 核心结果汇总

| 模块 / 流程 | 关键结果 | 说明 |
| --- | --- | --- |
| Embedding 初筛层 | 过滤约 60% - 70% 候选对 | 高置信相似约 10% - 20%，高置信不相似约 40% - 50% |
```

- 规则：
  - 标签行必须单独一行，格式是 `[[tbl:唯一标识]]`
  - 标签行后建议空一行，再写表题
  - 表题必须独立一行，不要把说明句和表题写在一行里
  - 表题文本必须以 `表 N ...` 开头
  - 正文解释和表题分开写

### 5. 图表交叉引用

- 正文引用图片：

```md
如 [[ref:fig:system_funnel]] 所示，整个系统采用漏斗式架构。
```

- 正文引用表格：

```md
核心结果见 [[ref:tbl:core_results]]。
```

- 规则：
  - 图片引用写成 `[[ref:fig:标识]]`
  - 表格引用写成 `[[ref:tbl:标识]]`
  - `标识` 必须和上面的标签行一致

### 6. 摘要与关键词

- 中文摘要、中文关键词、英文摘要、英文关键词只写在 `report/metadata.json`
- 不要在 `manuscript.md` 里重复写摘要页内容

## 质量要求

- 不要留下默认 Word 样式
- 不要把版式规则分散写在多个地方，应优先修改 profile JSON
- 目录和页码必须是 Word 字段，便于更新
- 参考文献不能残留未解析的 citekey
- 参考文献默认使用统一左对齐与固定行距；如果要调整编号、缩进或间距，应直接修改 `assets/profiles/course-paper.json` 中的 `reference` 样式

## 交接说明

- 如果用户给了新的学校模板，应新增同级 profile
- 如果用户要换引用格式，优先替换 CSL，不要改动正文源格式
- 完成后要明确告诉用户应修改哪个 profile 文件以便复用

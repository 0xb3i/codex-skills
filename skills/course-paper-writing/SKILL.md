---
name: course-paper-writing
description: 当任务是撰写、续写或重写中文课程论文 Markdown，并且需要每次修改后都编译成最终版 docx 时使用；这个 skill 负责写作工作流，上层只需遵守固定 Markdown 规范并调用封装脚本，底层排版交给 thesis-docx。
---

# Course Paper Writing

## 概述

这个 skill 是写作层工作流，负责驱动“写 Markdown -> 编译 DOCX -> 根据成稿继续改 Markdown”的循环。它不直接处理复杂排版细节，而是把编译与排版委托给底层 `thesis-docx` skill。

## 什么时候用

- 需要从 0 开始写一篇中文课程论文。
- 需要在已有 `report/manuscript.md` 基础上续写或改写。
- 需要每完成一轮正文修改，就立刻看到最新 `report/report.docx` 的最终版效果。
- 需要保证写作输出天然兼容 `thesis-docx` 的编译要求，而不是后面再返工格式。

## 固定流程

1. 先读 `references/markdown-spec.md`，按其中的格式写 `report/manuscript.md`。
2. 再读 `references/writing-style.md`，按中文课程论文风格组织表达。
3. 修改源文件时，只改这三类文件：
   - `report/manuscript.md`
   - `report/metadata.json`
   - `report/references.bib`
4. 每轮有实质修改后，运行：

```bash
zsh "$SKILL_DIR/scripts/build-report-docx.sh"
```

5. 该脚本会同时生成：
   - `report/report.docx`
   - `report/report.pdf`
6. 打开 `report/report.docx` 和 `report/report.pdf` 检查结构、目录、图表、引用、分页，再继续回改源文件。

## 源文件约束

- 不要手工改 `report/report.docx`
- 不要在 Markdown 中写封面、目录、页码
- 不要手写 `[1]`、`[2]` 这类文献编号
- 不要在正文末尾手写参考文献列表
- 不要把图表标签和图片/表题混在同一段

## 封装命令

先确定 skill 路径：

```bash
if [ -d codex-skills/course-paper-writing ]; then
  SKILL_DIR="codex-skills/course-paper-writing"
else
  SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/course-paper-writing"
fi
```

然后构建最终文档：

```bash
zsh "$SKILL_DIR/scripts/build-report-docx.sh"
```

## 资源

- `references/markdown-spec.md`
  定义标题、图片、表格、题注、交叉引用、文献引用的 Markdown 格式。
- `references/writing-style.md`
  定义中文课程论文的表达风格、段落组织和章节写法。
- `scripts/build-report-docx.sh`
  封装好的编译命令，先调用底层 `thesis-docx` 生成 `report/report.docx`，再自动导出 `report/report.pdf`。

## 交接规则

- 写作层只关心 Markdown 规范和构建命令，不要展开底层排版实现。
- 遇到版式问题，去改底层 `thesis-docx` 的 profile 或脚本，不要在本 skill 里绕过。
- 每次正文发生实质修改后，都重新生成一次 `report/report.docx`。

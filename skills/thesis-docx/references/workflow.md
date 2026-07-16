# 工作流

## 推荐路径

1. 在 Markdown 中撰写正文。
2. 在 `.bib` 文件中维护参考文献。
3. 使用 `scripts/thesis_docx.py build --markdown ... --bib ...`，让 Pandoc 负责章节编号、引用与参考文献。
4. 让同一个脚本重新打开 DOCX，并套用共享的排版 profile。
5. 使用 `scripts/export-docx-pdf.sh` 自动导出 PDF。
6. 在 Word 或 WPS 中更新一次字段，刷新目录和页码。

## 什么时候用空白骨架路径

在以下情况使用 `build --metadata ...`：

- 你想先生成一个可直接编辑的论文壳子。
- 当前环境没有 Pandoc。
- 你准备直接在 Word 里写正文。

## 什么时候用重排路径

在以下情况使用 `restyle --input ...`：

- 内容已经存在于 `.docx` 中。
- 当前版式不统一。
- 你想在交付前快速统一整份文档的模板风格。

## 引用说明

- 最稳定的自动化方案是 Pandoc + BibTeX/CSL。
- 如果你直接在 Word 中写作，仍可使用 `restyle` 模式，但参考文献生成就不再由本脚本负责，而要依赖 Word、Zotero、EndNote 或人工维护。
- 最终 DOCX 中不能残留未解析的 citekey，例如 `[@smith2024]`。

## 目录与字段

脚本会插入 Word 目录字段和页码字段，并设置为打开文档时尝试刷新。实际导出前，Word 或 WPS 仍可能需要你手动更新一次字段。

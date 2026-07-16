# 引言

在这里撰写正文。若采用内容优先工作流，可以先使用 `pandoc` 将 Markdown 与 BibTeX 编译为原始 DOCX，再使用 `thesis_docx.py restyle` 套用课程论文 profile。引用示例见文献 [@vaswani2017attention]。

# 模板映射设计

说明如何将 LaTeX 模板中的页面、字体、字号、摘要、目录、页眉页脚、参考文献与附录迁移到 DOCX。

## 页面与字体

复旦大学课程论文模板默认使用 A4 纸张，上边距 22mm，下边距 20mm，左右边距 27mm；正文中文字体使用思源宋体，英文字体使用 Times New Roman。

## 引用

数值型引用通过 Pandoc 与 CSL/BibTeX 协同生成。当前课程论文 profile 默认启用 `GB/T 7714-2015` numeric CSL，可输出上标数字引用，并在支持的 DOCX 阅读器中提供跳转到参考文献条目的内部链接 [@vaswani2017attention]。

# 实现流程

介绍 Markdown、BibTeX、Pandoc 与 DOCX 后处理脚本在工作流中的角色分工。

# 结论

总结模板 profile 的复用方式。

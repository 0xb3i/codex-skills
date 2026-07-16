#!/bin/zsh
set -euo pipefail

if [ -d codex-skills/thesis-docx ]; then
  THESIS_SKILL_DIR="codex-skills/thesis-docx"
else
  THESIS_SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/thesis-docx"
fi

.venv/bin/python "$THESIS_SKILL_DIR/scripts/thesis_docx.py" build \
  --metadata report/metadata.json \
  --markdown report/manuscript.md \
  --bib report/references.bib \
  --spec "$THESIS_SKILL_DIR/assets/profiles/course-paper.json" \
  --no-toc \
  --output report/report.docx

zsh "$THESIS_SKILL_DIR/scripts/export-docx-pdf.sh" report/report.docx report/report.pdf

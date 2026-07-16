#!/bin/zsh
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: export-docx-pdf.sh <input.docx> <output.pdf>" >&2
  exit 1
fi

INPUT_DOCX="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
OUTPUT_PDF="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
OUTPUT_DIR="$(dirname "$OUTPUT_PDF")"
BASENAME_NO_EXT="$(basename "$OUTPUT_PDF" .pdf)"

mkdir -p "$OUTPUT_DIR"
rm -f "$OUTPUT_PDF"

if command -v soffice >/dev/null 2>&1; then
  soffice --headless --convert-to pdf --outdir "$OUTPUT_DIR" "$INPUT_DOCX" >/dev/null
  GENERATED_PDF="$OUTPUT_DIR/$(basename "$INPUT_DOCX" .docx).pdf"
  if [ -f "$GENERATED_PDF" ] && [ "$GENERATED_PDF" != "$OUTPUT_PDF" ]; then
    mv "$GENERATED_PDF" "$OUTPUT_PDF"
  fi
elif command -v libreoffice >/dev/null 2>&1; then
  libreoffice --headless --convert-to pdf --outdir "$OUTPUT_DIR" "$INPUT_DOCX" >/dev/null
  GENERATED_PDF="$OUTPUT_DIR/$(basename "$INPUT_DOCX" .docx).pdf"
  if [ -f "$GENERATED_PDF" ] && [ "$GENERATED_PDF" != "$OUTPUT_PDF" ]; then
    mv "$GENERATED_PDF" "$OUTPUT_PDF"
  fi
elif command -v osascript >/dev/null 2>&1; then
  osascript <<EOF
set inputPath to POSIX file "$INPUT_DOCX"
set outputPath to POSIX file "$OUTPUT_PDF"
tell application "Microsoft Word"
  activate
  open inputPath
  set docRef to active document
  save as docRef file name outputPath file format format PDF
  close docRef saving no
end tell
EOF
else
  echo "No supported DOCX to PDF converter found." >&2
  exit 1
fi

if [ ! -f "$OUTPUT_PDF" ]; then
  echo "Failed to generate PDF: $OUTPUT_PDF" >&2
  exit 1
fi

echo "Generated: $OUTPUT_PDF"

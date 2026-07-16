---
name: docx-template-fill
description: Use when filling an existing Word .docx template, form, interview template, table template, or questionnaire where the output must preserve the template's original fonts, colors, widths, headers, watermarks, borders, spacing, or page layout.
---

# DOCX Template Fill

## Core Rule

Treat the input `.docx` as the source of truth for layout and formatting. Fill text into the existing structure; do not redesign, restyle, resize, add title blocks, change margins, or rebuild tables unless the user explicitly asks.

## Workflow

1. Use `documents:documents` for DOCX handling and visual render QA.
2. Inspect the template first: paragraphs, tables, rows, cells, merged cells, and representative run fonts.
3. Copy the template table/section for repeated entries instead of constructing a new table.
4. Replace only the target text. Preserve `tcPr`, `pPr`, `rPr`, table grid, borders, shading, headers, footers, watermarks, and section properties.
5. For blank target cells, use a nearby filled answer cell as the fallback run style. Blank cells often have no run formatting, so default `python-docx` text insertion will use the wrong font.
6. Render the final DOCX to PNG pages and inspect for font drift, width drift, blank pages, clipped text, broken tables, and page-order issues.

## Filling Cells Without Losing Style

Avoid `cell.text = value` and avoid clearing/rebuilding paragraphs with new runs unless you manually clone the original style. Those APIs commonly erase run-level fonts or cause blank cells to fall back to default fonts.

Use this pattern when filling table cells:

```python
from copy import deepcopy
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def _first_rpr(cell):
    for p in cell._tc.xpath('./w:p'):
        for r in p.xpath('./w:r'):
            r_pr = r.find(qn('w:rPr'))
            if r_pr is not None:
                return deepcopy(r_pr)
    return None


def set_cell_text_preserve(cell, text, fallback_cell=None):
    first_p = cell._tc.xpath('./w:p')[0] if cell._tc.xpath('./w:p') else OxmlElement('w:p')
    p_pr = first_p.find(qn('w:pPr'))
    first_r = first_p.find(qn('w:r'))
    r_pr = first_r.find(qn('w:rPr')) if first_r is not None else None
    if r_pr is None and fallback_cell is not None:
        r_pr = _first_rpr(fallback_cell)

    for child in list(cell._tc):
        if child.tag != qn('w:tcPr'):
            cell._tc.remove(child)

    for line in str(text).split('\n') or ['']:
        p = OxmlElement('w:p')
        if p_pr is not None:
            p.append(deepcopy(p_pr))
        r = OxmlElement('w:r')
        if r_pr is not None:
            r.append(deepcopy(r_pr))
        t = OxmlElement('w:t')
        if line.startswith(' ') or line.endswith(' '):
            t.set(qn('xml:space'), 'preserve')
        t.text = line
        r.append(t)
        p.append(r)
        cell._tc.append(p)
```

For repeated template sections, keep a clean copy before filling:

```python
clean_table = deepcopy(doc.tables[0])
table = deepcopy(clean_table)
```

Insert copied tables before `sectPr` and add page breaks explicitly; appending after the section properties can create blank pages or strange ordering.

## Formatting Checks

- Compare source and output table widths, row count, column count, header/footer presence, and first-page visual layout.
- Check empty-template fields after filling: they are the highest-risk font drift points.
- If the user says “完全按照模板”, “字体不对”, “宽度不对”, “不要自由发挥”, or similar, make no cosmetic edits beyond content replacement.
- Keep unknown fields blank or marked exactly as requested; do not invent personal data unless the user says to generate it.

## Common Mistakes

- Adding a new title above the template when the template already has one.
- Changing page margins to fit content instead of letting the template paginate naturally.
- Using bullet/list styles that are not present in the template.
- Changing a merged header cell and accidentally flattening mixed run fonts.
- Filling blank cells without a fallback style, causing font mismatch.

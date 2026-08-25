# -*- coding: utf-8 -*-
"""Builds Presentation/KPI_BSP_Calculation_Reference.docx from content.py."""
import os
import sys

from docx import Document
from docx.shared import Pt, Inches, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

sys.path.insert(0, os.path.dirname(__file__))
import content as C

NAVY = RGBColor(0x1F, 0x2D, 0x50)
ACCENT = RGBColor(0x2E, 0x6F, 0x95)
GRAY = RGBColor(0x55, 0x55, 0x55)
LIGHT_BG = "EFF3F6"
CALLOUT_BG = "FFF4E5"

OUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "KPI_BSP_Calculation_Reference.docx",
)


def shade_cell(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def set_cell_text(cell, text, bold=False, size=10, color=None, align=None):
    cell.text = ""
    p = cell.paragraphs[0]
    run = p.add_run(str(text))
    run.bold = bold
    run.font.size = Pt(size)
    if color:
        run.font.color.rgb = color
    if align:
        p.alignment = align


def add_heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = NAVY
    return h


def add_body(doc, text, size=10.5, italic=False, bold=False, color=None, space_after=8):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.italic = italic
    run.bold = bold
    if color:
        run.font.color.rgb = color
    p.paragraph_format.space_after = Pt(space_after)
    return p


def add_bullets(doc, items, size=10.5):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        run = p.add_run(item)
        run.font.size = Pt(size)
        p.paragraph_format.space_after = Pt(4)


def add_callout(doc, title, paragraphs, bullets=None):
    """A shaded one-cell 'table' used as a callout box."""
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.cell(0, 0)
    shade_cell(cell, CALLOUT_BG)
    cell.text = ""
    p0 = cell.paragraphs[0]
    r0 = p0.add_run(title)
    r0.bold = True
    r0.font.size = Pt(11)
    r0.font.color.rgb = NAVY
    for para in paragraphs:
        p = cell.add_paragraph()
        r = p.add_run(para)
        r.font.size = Pt(10)
    if bullets:
        for b in bullets:
            p = cell.add_paragraph(style="List Bullet")
            r = p.add_run(b)
            r.font.size = Pt(10)
    doc.add_paragraph()  # spacer


def add_kv_table(doc, rows, label_width=1.6):
    """rows: list of (label, value) -- value may be str or list[str]."""
    table = doc.add_table(rows=0, cols=2)
    table.style = "Light Grid Accent 1"
    table.autofit = True
    for label, value in rows:
        row = table.add_row()
        set_cell_text(row.cells[0], label, bold=True, size=9.5, color=NAVY)
        row.cells[0].width = Inches(label_width)
        if isinstance(value, list):
            row.cells[1].text = ""
            for i, line in enumerate(value):
                p = row.cells[1].paragraphs[0] if i == 0 else row.cells[1].add_paragraph()
                r = p.add_run(("• " if len(value) > 1 else "") + line)
                r.font.size = Pt(9.5)
        else:
            set_cell_text(row.cells[1], value, size=9.5)
    doc.add_paragraph()
    return table


def add_kpi_section(doc, kpi, idx):
    add_heading(doc, f"{idx}. {kpi['name']}", level=2)
    meta = doc.add_paragraph()
    r = meta.add_run(f"Category: {kpi['category']}    |    Direction: {kpi['direction']}")
    r.italic = True
    r.font.size = Pt(9.5)
    r.font.color.rgb = ACCENT
    meta.paragraph_format.space_after = Pt(6)

    add_body(doc, "What it measures:", bold=True, size=10, space_after=2)
    add_body(doc, kpi["measures"], space_after=8)

    rows = [
        ("Formula", kpi["formula"]),
        ("Numerator", kpi["numerator"]),
        ("Denominator", kpi["denominator"]),
        ("Filters", kpi["filters"]),
        ("Actual Performance", kpi["actual"]),
        ("BSP (benchmark)", kpi["bsp"]),
        ("BSP Performance", kpi["bsp_performance"]),
        ("Sheet Gap formula", kpi["sheet_gap_formula"]),
        ("Special Logic", kpi["special_logic"]),
    ]
    add_kv_table(doc, rows)

    ex = kpi["example"]
    add_body(doc, "Worked example:", bold=True, size=10, space_after=2)
    ex_table = doc.add_table(rows=0, cols=1)
    ex_table.style = "Light List Accent 1"
    for key in ("actual", "bsp", "inputs", "calc", "result"):
        if key in ex:
            row = ex_table.add_row()
            set_cell_text(row.cells[0], ex[key], size=9.5)
    doc.add_paragraph()


def build():
    doc = Document()

    # Base style
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)

    # ---- Title page ----
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_p.add_run(C.DOC_TITLE)
    title_run.font.size = Pt(28)
    title_run.font.bold = True
    title_run.font.color.rgb = NAVY

    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_run = sub_p.add_run(C.DOC_SUBTITLE)
    sub_run.font.size = Pt(13)
    sub_run.font.color.rgb = ACCENT

    doc.add_paragraph()
    note_p = doc.add_paragraph()
    note_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    note_run = note_p.add_run(
        "Prepared for a plant working session. All calculations described are "
        "sourced directly from the production calculation script "
        "(InsightOpexv1.qvs). This document is a discussion basis, not a "
        "final declaration that the current methodology is correct."
    )
    note_run.italic = True
    note_run.font.size = Pt(10)
    note_run.font.color.rgb = GRAY

    doc.add_page_break()

    # ---- 1. Purpose ----
    add_heading(doc, "1. Purpose", level=1)
    for para in C.PURPOSE_PARAGRAPHS:
        add_body(doc, para)

    # ---- 2. How to Read This Document ----
    add_heading(doc, "2. How to Read This Document", level=1)
    for para in C.HOW_TO_READ_PARAGRAPHS:
        add_body(doc, para)
    add_kv_table(doc, C.HOW_TO_READ_TERMS, label_width=1.9)

    add_callout(doc, C.SCOPE_CALLOUT_TITLE, C.SCOPE_CALLOUT_PARAGRAPHS, C.SCOPE_CALLOUT_BULLETS)

    # ---- 3. KPI Overview ----
    add_heading(doc, "3. KPI Overview", level=1)
    add_body(doc, "Ten KPIs are currently published in the weekly report: one Outcome "
                  "(OEE) and nine Levers/Sub-levers that explain what drove OEE. "
                  "The table below is a quick-reference index; full detail for each "
                  "KPI follows in Section 4.")
    ov_table = doc.add_table(rows=1, cols=4)
    ov_table.style = "Light Grid Accent 1"
    hdr = ov_table.rows[0].cells
    for i, h in enumerate(["KPI", "Category", "Direction", "What it measures (short)"]):
        set_cell_text(hdr[i], h, bold=True, size=9.5, color=RGBColor(0xFF, 0xFF, 0xFF))
        shade_cell(hdr[i], "1F2D50")
    for kpi in C.KPIS:
        row = ov_table.add_row().cells
        set_cell_text(row[0], kpi["name"], bold=True, size=9)
        set_cell_text(row[1], kpi["category"], size=9)
        set_cell_text(row[2], kpi["direction"], size=9)
        short = kpi["measures"].split(". ")[0]
        set_cell_text(row[3], short, size=9)
    doc.add_paragraph()

    doc.add_page_break()

    # ---- 4. KPI-by-KPI Calculations ----
    add_heading(doc, "4. KPI-by-KPI Calculations", level=1)
    add_body(doc, "Each KPI below follows the same structure so they can be compared "
                  "side by side during the working session.")
    for i, kpi in enumerate(C.KPIS, start=1):
        add_kpi_section(doc, kpi, i)

    doc.add_page_break()

    # ---- 5. BSP Calculation — Detailed Explanation ----
    add_heading(doc, "5. BSP Calculation — Detailed Explanation", level=1)
    add_body(doc, "This section explains the mechanism common to every KPI's BSP "
                  "(unless that KPI's own section calls out a difference).")
    for title, text in C.BSP_MECHANISM_STEPS:
        add_body(doc, title, bold=True, size=10.5, space_after=2)
        add_body(doc, text, space_after=10)

    add_heading(doc, "5.1 The 13-point BSP checklist, answered once", level=2)
    add_body(doc, C.BSP_CHECKLIST_HEADER)
    add_kv_table(doc, C.BSP_CHECKLIST_COMMON, label_width=2.3)

    doc.add_page_break()

    # ---- 6. Special BSP Logic ----
    add_heading(doc, "6. Special BSP Logic", level=1)
    add_body(doc, "Every published KPI uses the standard 3-level percentile mechanism "
                  "described in Section 5, with one exception: Scrap Loss. See Section 7 "
                  "for the full explanation. No other KPI in the script uses a "
                  "materially different BSP mechanism as of this review; the "
                  "KPI-specific variations that do exist (narrower grain for Avg MR "
                  "Time; zero-event-inclusive pool for the per-10K KPIs) are called "
                  "out in each KPI's Special Logic field in Section 4.")

    # ---- 7. Scrap / Expected Scrap ----
    add_heading(doc, "7. Scrap / Expected Scrap Calculation", level=1)
    add_heading(doc, C.SCRAP_SPECIAL_TITLE, level=2)
    add_body(doc, "Why this KPI works differently:", bold=True, size=10, space_after=2)
    add_body(doc, C.SCRAP_SPECIAL_WHY, space_after=10)
    for title, text in C.SCRAP_SPECIAL_STEPS:
        add_body(doc, title, bold=True, size=10.5, space_after=2)
        add_body(doc, text, space_after=10)

    add_body(doc, "Worked example:", bold=True, size=10, space_after=2)
    ex = C.SCRAP_SPECIAL_EXAMPLE
    ex_table = doc.add_table(rows=0, cols=1)
    ex_table.style = "Light List Accent 1"
    for key in ("setup", "bench", "expected", "actual", "gap"):
        row = ex_table.add_row()
        set_cell_text(row.cells[0], ex[key], size=9.5)
    doc.add_paragraph()
    add_body(doc, ex["note"], italic=True, size=9.5)

    doc.add_page_break()

    # ---- 8. Sheet Gap ----
    add_heading(doc, "8. Sheet Gap Calculation", level=1)
    add_body(doc, C.SHEET_GAP_INTRO)
    add_kv_table(doc, C.SHEET_GAP_POINTS, label_width=2.1)
    add_body(doc, C.SHEET_GAP_HISTORICAL_NOTE, italic=True)

    add_body(doc, "Worked example (OEE row):", bold=True, size=10, space_after=2)
    sg = C.SHEET_GAP_EXAMPLE
    sg_table = doc.add_table(rows=0, cols=1)
    sg_table.style = "Light List Accent 1"
    for key in ("line1", "line2", "calc", "line3"):
        row = sg_table.add_row()
        set_cell_text(row.cells[0], sg[key], size=9.5)
    doc.add_paragraph()

    # ---- 9. Filters and Business Rules ----
    add_heading(doc, "9. Filters and Business Rules", level=1)
    add_body(doc, "Summary of the main filters, direction, BSP type, and special logic "
                  "across all published KPIs.")
    ft = doc.add_table(rows=1, cols=5)
    ft.style = "Light Grid Accent 1"
    hdr = ft.rows[0].cells
    for i, h in enumerate(["KPI", "Main Filters", "Direction", "BSP Type", "Special Logic"]):
        set_cell_text(hdr[i], h, bold=True, size=9, color=RGBColor(0xFF, 0xFF, 0xFF))
        shade_cell(hdr[i], "1F2D50")
    for row_data in C.FILTER_SUMMARY_TABLE:
        row = ft.add_row().cells
        for i, val in enumerate(row_data):
            set_cell_text(row[i], val, size=8.5)
    doc.add_paragraph()

    doc.add_page_break()

    # ---- 10. Worked Examples (consolidated) ----
    add_heading(doc, "10. Worked Examples — Consolidated", level=1)
    add_body(doc, "All worked examples from Sections 4, 7, and 8 use illustrative "
                  "figures to demonstrate the formula from the script; they are not "
                  "actual production numbers.")
    wt = doc.add_table(rows=1, cols=3)
    wt.style = "Light Grid Accent 1"
    hdr = wt.rows[0].cells
    for i, h in enumerate(["KPI", "Actual vs. BSP", "Sheet Gap"]):
        set_cell_text(hdr[i], h, bold=True, size=9.5, color=RGBColor(0xFF, 0xFF, 0xFF))
        shade_cell(hdr[i], "1F2D50")
    for kpi in C.KPIS:
        ex = kpi["example"]
        row = wt.add_row().cells
        set_cell_text(row[0], kpi["name"], bold=True, size=9)
        set_cell_text(row[1], f"{ex.get('actual','')} vs {ex.get('bsp','')}", size=9)
        set_cell_text(row[2], ex.get("result", ""), size=9)
    doc.add_paragraph()

    # ---- 11. Items for Plant Review / Discussion ----
    add_heading(doc, "11. Items for Plant Review / Discussion", level=1)
    add_body(doc, "These are areas of the current implementation that are working as "
                  "designed but may warrant plant confirmation or a business decision "
                  "to change. None of these are flagged as errors — they are "
                  "highlighted because a reasonable alternative exists and the current "
                  "choice reflects a design decision, not an obvious fact.")
    for i, (title, text) in enumerate(C.REVIEW_ITEMS, start=1):
        add_body(doc, f"{i}. {title}", bold=True, size=10.5, space_after=2)
        add_body(doc, text, space_after=8)

    doc.add_page_break()

    # ---- Dependencies ----
    add_heading(doc, "Dependencies Outside This Script", level=1)
    add_body(doc, "This script references several external data sources whose own "
                  "logic was not reviewed as part of this document — they are listed "
                  "here for completeness and traceability.")
    add_kv_table(doc, C.DEPENDENCIES, label_width=2.0)

    # ---- 12. Appendix ----
    add_heading(doc, "12. Appendix — Technical Source Mapping", level=1)
    add_body(doc, "For traceability only. Section numbers refer to the comment "
                  "headers inside InsightOpexv1.qvs. This is the only section of the "
                  "document that references the underlying script directly.")
    at = doc.add_table(rows=1, cols=2)
    at.style = "Light Grid Accent 1"
    hdr = at.rows[0].cells
    for i, h in enumerate(["Topic", "Script Section(s)"]):
        set_cell_text(hdr[i], h, bold=True, size=9.5, color=RGBColor(0xFF, 0xFF, 0xFF))
        shade_cell(hdr[i], "1F2D50")
    for topic, sect in C.APPENDIX_TRACE:
        row = at.add_row().cells
        set_cell_text(row[0], topic, size=9)
        set_cell_text(row[1], sect, size=9)

    doc.save(OUT_PATH)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    build()

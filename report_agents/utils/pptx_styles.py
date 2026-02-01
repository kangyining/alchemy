"""PPTX styling constants and helper functions."""

import re

from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

# Brand colors
PRIMARY_COLOR = RGBColor(0x1A, 0x3C, 0x6E)  # Dark navy
ACCENT_COLOR = RGBColor(0x2E, 0x86, 0xAB)  # Blue
TEXT_COLOR = RGBColor(0x33, 0x33, 0x33)  # Near-black
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xF2, 0xF2, 0xF2)

# Slide dimensions (16:9 widescreen)
SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)

# Layout constants
TITLE_BAR_HEIGHT = Inches(1.2)
CONTENT_TOP = Inches(1.5)
CONTENT_LEFT = Inches(0.75)
CONTENT_WIDTH = Inches(11.8)
CONTENT_HEIGHT = Inches(5.5)


def add_title_bar(slide, title_text: str):
    """Add a colored title bar at the top of a slide."""
    from pptx.enum.shapes import MSO_SHAPE

    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0),
        Inches(0),
        SLIDE_WIDTH,
        TITLE_BAR_HEIGHT,
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = PRIMARY_COLOR
    shape.line.fill.background()

    tf = shape.text_frame
    tf.text = title_text
    tf.paragraphs[0].font.size = Pt(28)
    tf.paragraphs[0].font.color.rgb = WHITE
    tf.paragraphs[0].font.bold = True
    tf.paragraphs[0].alignment = PP_ALIGN.LEFT
    tf.margin_left = Inches(0.5)
    tf.margin_top = Inches(0.25)


def _parse_md_table(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    """Parse markdown pipe-table lines into headers and rows.

    Returns (headers, body_rows) where each is a list of cell strings.
    Skips the separator row (e.g. |---|---|).
    """
    headers = []
    body = []
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        # Separator row — all cells are dashes/colons
        if all(re.match(r"^:?-+:?$", c) for c in cells):
            continue
        if not headers:
            headers = cells
        else:
            body.append(cells)
    return headers, body


def _add_table_shape(slide, headers: list[str], rows: list[list[str]],
                     left, top, width):
    """Add a styled PPTX table shape to the slide."""
    num_rows = 1 + len(rows)  # header + body
    num_cols = len(headers)
    if num_cols == 0:
        return top

    # Calculate row height to fit content
    row_height = Inches(0.35)
    table_height = row_height * num_rows

    table_shape = slide.shapes.add_table(
        num_rows, num_cols, left, top, width, table_height,
    )
    table = table_shape.table

    # Style header row
    for col_idx, header_text in enumerate(headers):
        cell = table.cell(0, col_idx)
        cell.text = header_text.replace("**", "")
        cell.fill.solid()
        cell.fill.fore_color.rgb = PRIMARY_COLOR
        p = cell.text_frame.paragraphs[0]
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = WHITE
        p.alignment = PP_ALIGN.CENTER

    # Style body rows
    for row_idx, row_cells in enumerate(rows):
        for col_idx, cell_text in enumerate(row_cells):
            if col_idx >= num_cols:
                break
            cell = table.cell(row_idx + 1, col_idx)
            cell.text = cell_text.replace("**", "")
            # Alternate row shading
            if row_idx % 2 == 1:
                cell.fill.solid()
                cell.fill.fore_color.rgb = LIGHT_GRAY
            p = cell.text_frame.paragraphs[0]
            p.font.size = Pt(10)
            p.font.color.rgb = TEXT_COLOR
            # Right-align numeric-looking cells, left-align first column
            if col_idx == 0:
                p.alignment = PP_ALIGN.LEFT
            else:
                p.alignment = PP_ALIGN.RIGHT

    return top + table_height + Inches(0.15)


def _render_text_lines(tf, lines: list[str], is_first_block: bool):
    """Render non-table markdown lines into a text frame."""
    for i, line in enumerate(lines):
        if i == 0 and is_first_block:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()

        stripped = line.strip()
        if not stripped:
            p.text = ""
            p.space_after = Pt(6)
            continue

        if stripped.startswith("## "):
            p.text = stripped[3:]
            p.font.size = Pt(20)
            p.font.bold = True
            p.font.color.rgb = PRIMARY_COLOR
            p.space_after = Pt(8)
        elif stripped.startswith("### "):
            p.text = stripped[4:]
            p.font.size = Pt(16)
            p.font.bold = True
            p.font.color.rgb = ACCENT_COLOR
            p.space_after = Pt(6)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            p.text = "  \u2022 " + stripped[2:]
            p.font.size = Pt(14)
            p.font.color.rgb = TEXT_COLOR
        elif stripped.startswith("**") and stripped.endswith("**"):
            p.text = stripped[2:-2]
            p.font.size = Pt(14)
            p.font.bold = True
            p.font.color.rgb = TEXT_COLOR
        else:
            p.text = stripped.replace("**", "")
            p.font.size = Pt(14)
            p.font.color.rgb = TEXT_COLOR


def render_markdown_to_textbox(slide, md_text: str, left=None, top=None, width=None, height=None):
    """Parse markdown and render into PPTX shapes.

    Text content goes into textboxes. Pipe tables (| col | col |) are
    rendered as actual PPTX table shapes with styled headers and rows.
    """
    left = left or CONTENT_LEFT
    top = top or CONTENT_TOP
    width = width or CONTENT_WIDTH
    height = height or CONTENT_HEIGHT

    # Split markdown into blocks: text blocks and table blocks
    lines = md_text.strip().split("\n")
    blocks = []  # list of (type, lines) where type is 'text' or 'table'
    current_text = []
    current_table = []

    for line in lines:
        stripped = line.strip()
        is_table_line = stripped.startswith("|") and stripped.endswith("|")

        if is_table_line:
            # Flush any pending text
            if current_text:
                blocks.append(("text", current_text))
                current_text = []
            current_table.append(stripped)
        else:
            # Flush any pending table
            if current_table:
                blocks.append(("table", current_table))
                current_table = []
            current_text.append(line)

    # Flush remaining
    if current_text:
        blocks.append(("text", current_text))
    if current_table:
        blocks.append(("table", current_table))

    # Render each block
    current_top = top
    is_first_text = True

    for block_type, block_lines in blocks:
        if block_type == "table":
            headers, rows = _parse_md_table(block_lines)
            if headers:
                current_top = _add_table_shape(
                    slide, headers, rows, left, current_top, width,
                )
        else:
            # Filter out empty-only blocks
            if all(not l.strip() for l in block_lines):
                continue
            remaining_height = (top + height) - current_top
            if remaining_height < Inches(0.5):
                break
            txBox = slide.shapes.add_textbox(
                left, current_top, width, remaining_height,
            )
            tf = txBox.text_frame
            tf.word_wrap = True
            _render_text_lines(tf, block_lines, is_first_text)
            is_first_text = False
            # Estimate height used (rough: 0.25in per line)
            current_top += Inches(0.25) * len(block_lines) + Inches(0.1)

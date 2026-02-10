"""PPTX styling constants and helper functions."""

import re

from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

# Brand colors
PRIMARY_COLOR = RGBColor(0x5B, 0x5B, 0x5B)  # Dark gray
ACCENT_COLOR = RGBColor(0xA8, 0x99, 0x68)  # Gold
TEXT_COLOR = RGBColor(0x11, 0x11, 0x11)  # Near-black
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xF2, 0xF2, 0xF2)

# Slide dimensions (Letter landscape)
SLIDE_WIDTH = Inches(11)
SLIDE_HEIGHT = Inches(8.5)

# Layout constants
TITLE_BAR_HEIGHT = Inches(1.2)
CONTENT_TOP = Inches(1.5)
CONTENT_LEFT = Inches(0.75)
CONTENT_WIDTH = Inches(9.5)
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
    tf.paragraphs[0].font.size = Pt(24)
    tf.paragraphs[0].font.color.rgb = WHITE
    tf.paragraphs[0].font.bold = True
    tf.paragraphs[0].font.name = "Arial"
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

    # Calculate row height to fit content (smaller for smaller fonts)
    row_height = Inches(0.28)
    table_height = row_height * num_rows

    table_shape = slide.shapes.add_table(
        num_rows, num_cols, left, top, width, table_height,
    )
    table = table_shape.table

    # Style header row
    for col_idx, header_text in enumerate(headers):
        cell = table.cell(0, col_idx)
        cell.text = _clean_markdown_text(header_text)
        cell.fill.solid()
        cell.fill.fore_color.rgb = PRIMARY_COLOR
        p = cell.text_frame.paragraphs[0]
        p.font.size = Pt(9)
        p.font.bold = True
        p.font.color.rgb = WHITE
        p.font.name = "Arial"
        p.alignment = PP_ALIGN.CENTER

    # Style body rows
    for row_idx, row_cells in enumerate(rows):
        for col_idx, cell_text in enumerate(row_cells):
            if col_idx >= num_cols:
                break
            cell = table.cell(row_idx + 1, col_idx)
            cell.text = _clean_markdown_text(cell_text)
            # Alternate row shading
            if row_idx % 2 == 1:
                cell.fill.solid()
                cell.fill.fore_color.rgb = LIGHT_GRAY
            p = cell.text_frame.paragraphs[0]
            p.font.size = Pt(8)
            p.font.color.rgb = TEXT_COLOR
            p.font.name = "Arial"
            # Right-align numeric-looking cells, left-align first column
            if col_idx == 0:
                p.alignment = PP_ALIGN.LEFT
            else:
                p.alignment = PP_ALIGN.RIGHT

    return top + table_height + Inches(0.15)


def _clean_markdown_text(text: str) -> str:
    """Remove all markdown syntax from text, keeping plain content."""
    # Remove inline code
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Remove bold/italic markers
    text = re.sub(r'\*\*\*([^*]+)\*\*\*', r'\1', text)  # ***bold italic***
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)      # **bold**
    text = re.sub(r'\*([^*]+)\*', r'\1', text)          # *italic*
    text = re.sub(r'___([^_]+)___', r'\1', text)        # ___bold italic___
    text = re.sub(r'__([^_]+)__', r'\1', text)          # __bold__
    text = re.sub(r'_([^_]+)_', r'\1', text)            # _italic_
    # Remove links [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove images ![alt](url)
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', text)
    return text


MUTED_COLOR = RGBColor(0x7A, 0x7A, 0x7A)

def _render_text_lines(tf, lines: list[str], is_first_block: bool):
    """Render non-table markdown lines into a text frame."""
    in_sources = False
    for i, line in enumerate(lines):
        if i == 0 and is_first_block:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()

        stripped = line.strip()

        # Detect start of Sources section (heading, bold, or plain)
        clean = _clean_markdown_text(stripped).strip()
        if stripped.startswith("#"):
            clean = stripped.lstrip("# ").strip()
        if re.match(r'^sources?\b', clean, re.IGNORECASE):
            in_sources = True

        if not stripped:
            p.text = ""
            p.space_after = Pt(2) if in_sources else Pt(4)
            continue

        if in_sources:
            # Skip horizontal rules
            if re.match(r'^[-_*]{3,}$', stripped):
                p.text = ""
                p.space_after = Pt(0)
                continue
            # Everything in Sources gets small muted text
            if stripped.startswith("#"):
                p.text = _clean_markdown_text(stripped.lstrip("# ").strip())
                p.font.size = Pt(4)
                p.font.bold = False
                p.font.color.rgb = MUTED_COLOR
                p.space_after = Pt(0)
            elif re.match(r'^[-*+]\s', stripped):
                p.text = "  \u2022 " + _clean_markdown_text(stripped[2:])
                p.font.size = Pt(4)
                p.font.color.rgb = MUTED_COLOR
            else:
                p.text = _clean_markdown_text(stripped)
                p.font.size = Pt(4)
                p.font.color.rgb = MUTED_COLOR
                p.font.name = "Arial"
            continue

        # Handle headers (# ## ### ####)
        if stripped.startswith("#### "):
            p.text = _clean_markdown_text(stripped[5:])
            p.font.size = Pt(11)
            p.font.bold = True
            p.font.color.rgb = ACCENT_COLOR
            p.space_after = Pt(4)
        elif stripped.startswith("### "):
            p.text = _clean_markdown_text(stripped[4:])
            p.font.size = Pt(12)
            p.font.bold = True
            p.font.color.rgb = ACCENT_COLOR
            p.space_after = Pt(4)
        elif stripped.startswith("## "):
            p.text = _clean_markdown_text(stripped[3:])
            p.font.size = Pt(14)
            p.font.bold = True
            p.font.color.rgb = PRIMARY_COLOR
            p.space_after = Pt(8)
        # Handle bullet points (-, *, +, or numbered 1. 2.)
        elif re.match(r'^[-*+]\s', stripped):
            p.text = "  \u2022 " + _clean_markdown_text(stripped[2:])
            p.font.size = Pt(10)
            p.font.color.rgb = TEXT_COLOR
        elif stripped.startswith("**") and stripped.endswith("**"):
            p.text = stripped[2:-2]
            p.font.size = Pt(14)
            p.font.bold = True
            p.font.color.rgb = TEXT_COLOR
        else:
            p.text = _clean_markdown_text(stripped)
            p.font.size = Pt(10)
            p.font.color.rgb = TEXT_COLOR
            p.font.name = "Arial"


def _strip_code_fences(md_text: str) -> str:
    """Remove markdown code fence wrappers like ```markdown ... ```."""
    text = md_text.strip()
    # Remove opening fence (```markdown, ```md, or just ```)
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
    # Remove closing fence
    if text.rstrip().endswith("```"):
        text = text.rstrip()[:-3].rstrip()
    return text


def _split_markdown_blocks(md_text: str):
    """Split markdown into blocks of (type, lines) where type is 'text' or 'table'."""
    # First strip any code fence wrappers
    md_text = _strip_code_fences(md_text)
    lines = md_text.strip().split("\n")
    blocks = []
    current_text = []
    current_table = []

    for line in lines:
        stripped = line.strip()
        is_table_line = stripped.startswith("|") and stripped.endswith("|")

        if is_table_line:
            if current_text:
                blocks.append(("text", current_text))
                current_text = []
            current_table.append(stripped)
        else:
            if current_table:
                blocks.append(("table", current_table))
                current_table = []
            current_text.append(line)

    if current_text:
        blocks.append(("text", current_text))
    if current_table:
        blocks.append(("table", current_table))

    return blocks


def _blocks_to_markdown(blocks) -> str:
    """Reconstruct markdown text from blocks."""
    lines = []
    for _, block_lines in blocks:
        lines.extend(block_lines)
    return "\n".join(lines)


def render_markdown_to_textbox(slide, md_text: str, left=None, top=None, width=None, height=None) -> str:
    """Parse markdown and render into PPTX shapes.

    Text content goes into textboxes. Pipe tables (| col | col |) are
    rendered as actual PPTX table shapes with styled headers and rows.

    Returns:
        Remaining markdown text that did not fit on the slide, or empty
        string if everything was rendered.
    """
    left = left or CONTENT_LEFT
    top = top or CONTENT_TOP
    width = width or CONTENT_WIDTH
    height = height or CONTENT_HEIGHT

    blocks = _split_markdown_blocks(md_text)

    # Render each block
    current_top = top
    is_first_text = True
    bottom = top + height

    for i, (block_type, block_lines) in enumerate(blocks):
        if block_type == "table":
            headers, rows = _parse_md_table(block_lines)
            if headers:
                # Estimate table height before adding
                table_height = Inches(0.28) * (1 + len(rows)) + Inches(0.15)
                remaining_height = bottom - current_top
                if table_height > remaining_height and i > 0:
                    # Table doesn't fit — return remaining blocks
                    return _blocks_to_markdown(blocks[i:])
                current_top = _add_table_shape(
                    slide, headers, rows, left, current_top, width,
                )
        else:
            # Filter out empty-only blocks
            if all(not l.strip() for l in block_lines):
                continue
            remaining_height = bottom - current_top
            # Estimate height per line, accounting for text wrapping
            # Base line height for 10pt font + extra for long lines that wrap
            base_line_height = Inches(0.22)
            # Estimate wrapped lines: ~80 chars fit per line at 10pt in 11.8in width
            chars_per_line = 100
            total_lines = 0
            for line in block_lines:
                line_len = len(line.strip())
                wrapped_lines = max(1, (line_len + chars_per_line - 1) // chars_per_line)
                total_lines += wrapped_lines
            estimated_height = base_line_height * total_lines + Inches(0.1)

            # Not enough space at all - return remaining
            if remaining_height < Inches(0.4) and i > 0:
                return _blocks_to_markdown(blocks[i:])

            # If text block is too tall, figure out how many lines fit
            if estimated_height > remaining_height:
                # Calculate how many source lines can fit by accumulating heights
                available = remaining_height - Inches(0.1)
                fit_lines = []
                for line in block_lines:
                    line_len = len(line.strip())
                    wrapped = max(1, (line_len + chars_per_line - 1) // chars_per_line)
                    line_height = base_line_height * wrapped
                    if available >= line_height or len(fit_lines) == 0:
                        fit_lines.append(line)
                        available -= line_height
                    else:
                        break

                if len(fit_lines) < len(block_lines):
                    overflow_lines = block_lines[len(fit_lines):]

                    txBox = slide.shapes.add_textbox(
                        left, current_top, width, remaining_height,
                    )
                    tf = txBox.text_frame
                    tf.word_wrap = True
                    _render_text_lines(tf, fit_lines, is_first_text)

                    # Return overflow: remaining lines from this block + subsequent blocks
                    overflow_blocks = [("text", overflow_lines)] + blocks[i + 1:]
                    return _blocks_to_markdown(overflow_blocks)

            txBox = slide.shapes.add_textbox(
                left, current_top, width, remaining_height,
            )
            tf = txBox.text_frame
            tf.word_wrap = True
            _render_text_lines(tf, block_lines, is_first_text)
            is_first_text = False
            # Estimate height used
            current_top += estimated_height

    return ""

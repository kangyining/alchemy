"""PPTX styling constants and helper functions."""

from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

# Brand colors
PRIMARY_COLOR = RGBColor(0x1A, 0x3C, 0x6E)  # Dark navy
ACCENT_COLOR = RGBColor(0x2E, 0x86, 0xAB)  # Blue
TEXT_COLOR = RGBColor(0x33, 0x33, 0x33)  # Near-black
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

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


def render_markdown_to_textbox(slide, md_text: str, left=None, top=None, width=None, height=None):
    """Parse markdown and render into a python-pptx text box with basic formatting."""
    left = left or CONTENT_LEFT
    top = top or CONTENT_TOP
    width = width or CONTENT_WIDTH
    height = height or CONTENT_HEIGHT

    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True

    lines = md_text.strip().split("\n")
    for i, line in enumerate(lines):
        if i == 0:
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
            # Strip inline bold markers for simple rendering
            p.text = stripped.replace("**", "")
            p.font.size = Pt(14)
            p.font.color.rgb = TEXT_COLOR

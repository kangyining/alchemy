"""Report assembly: builds PPTX and PDF from slide agent outputs."""

import base64
import io
import json
import logging
from datetime import datetime
from pathlib import Path

import markdown as md_lib
from jinja2 import Template
from pptx import Presentation
from pptx.util import Inches, Pt
from weasyprint import HTML

from google.genai import types as genai_types

from report_agents.prompts.registry import SLIDE_REGISTRY, SlideType
from report_agents.utils.pptx_styles import (
    SLIDE_WIDTH,
    SLIDE_HEIGHT,
    CONTENT_LEFT,
    CONTENT_TOP,
    CONTENT_WIDTH,
    CONTENT_HEIGHT,
    PRIMARY_COLOR,
    ACCENT_COLOR,
    TEXT_COLOR,
    WHITE,
    add_title_bar,
    render_markdown_to_textbox,
)
from report_agents.utils.state_keys import slide_content_key, slide_chart_image_key

logger = logging.getLogger(__name__)


# PDF HTML template
ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
INFINITY_TEXT_LOGO_SVG_PATH = ASSETS_DIR / "infinity-text-logo.svg"
try:
    INFINITY_TEXT_LOGO_SVG = INFINITY_TEXT_LOGO_SVG_PATH.read_text(encoding="utf-8")
except Exception as exc:
    logger.warning("Infinity text logo SVG not available: %s", exc)
    INFINITY_TEXT_LOGO_SVG = ""

INFINITY_LOGO_PNG_PATH = ASSETS_DIR / "infinity-logo.png"
try:
    INFINITY_LOGO_PNG_BYTES = INFINITY_LOGO_PNG_PATH.read_bytes()
    INFINITY_LOGO_PNG_B64 = base64.b64encode(INFINITY_LOGO_PNG_BYTES).decode("utf-8")
except Exception as exc:
    logger.warning("Infinity logo PNG not available: %s", exc)
    INFINITY_LOGO_PNG_BYTES = None
    INFINITY_LOGO_PNG_B64 = ""

PDF_TEMPLATE = Template("""<!DOCTYPE html>
<html>
<head>
<style>
  @page { size: 13.333in 7.5in; margin: 0; }
  :root {
    --ink: #111111;
    --muted: #7a7a7a;
    --accent: #A89968;
    --bar: #5b5b5b;
    --light: #f2f2f2;
    --grid: #e5e5e5;
  }
  body { font-family: Arial, Helvetica, sans-serif; color: var(--ink); line-height: 1.3; margin: 0; padding: 0; }
  .slide { 
    page-break-after: always; 
    width: 13.33in; /* Matching SLIDE_WIDTH */
    height: 7.5in;   /* Matching SLIDE_HEIGHT */
    position: relative; 
    overflow: hidden;
    padding-right: 0.5in; /* Add safe buffer on the right */
    box-sizing: border-box;
  }
  .slide:last-child { page-break-after: avoid; }
  
  .title-bar {
    background-color: var(--bar);
    color: white;
    height: 0.6in;
    display: flex;
    align-items: center;
    padding: 0 0.5in;
    font-size: 24pt;
    font-weight: bold;
    text-transform: capitalize;
    margin-right: -0.5in; /* Offset slide padding for title bar */
  }

  .content-area {
    padding: 0.25in 0.5in 0.25in 0.5in;
    height: 6.9in;
    box-sizing: border-box;
  }

  .content { font-size: 11pt; }
  p { margin: 0 0 8px 0; }
  ul { margin: 0 0 10px 18px; }
  li { margin: 2px 0; }
  
  table { 
    border-collapse: collapse; 
    width: 100%; 
    max-width: 100%; 
    margin: 8px 0; 
    table-layout: fixed; /* Force columns to stay in box */
    box-sizing: border-box; 
  }
  th, td { 
    border: 1px solid var(--grid); 
    padding: 6px 8px; 
    font-size: 9.5pt; 
    word-wrap: break-word;
    overflow-wrap: break-word;
  }
  th { background: var(--bar); color: #ffffff; text-align: center; }
  td { text-align: left; }
  tr:nth-child(even) { background: #f9f9f9; }
 
  /* Cover layout */
  .cover { background: white; padding: 0.75in; box-sizing: border-box; }
  .cover-stack {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    height: 6in;
  }
  .cover-date { font-size: 14pt; letter-spacing: 0.08em; text-transform: uppercase; }
  .cover-title { color: var(--accent); font-size: 24pt; font-weight: bold; margin: 2in 0; }
  .cover-branding svg { height: 60px; }
  .cover-infinity-logo {
    position: absolute;
    right: 0.5in;
    bottom: 0.5in;
    height: 100px;
  }

  /* Utility to remove h2 from inner markdown if it's already in title bar */
  .inner-content h2 { display: none; }
  .inner-content strong, .inner-content b { font-weight: bold; }

  /* Chart slides: chart fills remaining content area below text/table */
  .slide-has-chart .content-area .inner-content {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
  }
  .slide-has-chart .content-area .inner-content > img {
    width: 100%;
    flex: 1;
    min-height: 0;
    object-fit: contain;
    object-position: top left;
  }
</style>
</head>
<body>
{% for section in sections %}
<div class="slide slide-{{ section.slide_number }}{% if section.is_cover %} cover{% endif %}{% if section.chart_img %} slide-has-chart{% endif %}">
  {% if section.is_cover %}
    <div class="cover-stack">
      <div class="cover-date">{{ section.cover_date }}</div>
      <div class="cover-title">{{ section.cover_title }}</div>
      {% if section.cover_logo_svg %}
      <div class="cover-branding">{{ section.cover_logo_svg }}</div>
      {% endif %}
    </div>
    {% if section.infinity_logo_png %}
    <img class="cover-infinity-logo" src="data:image/png;base64,{{ section.infinity_logo_png }}" />
    {% endif %}
  {% else %}
    <div class="title-bar">{{ section.title }}</div>
    <div class="content-area">
      <div class="inner-content">
        {{ section.html_content }}
        {% if section.chart_img %}
        <img src="data:image/png;base64,{{ section.chart_img }}" alt="Chart" />
        {% endif %}
      </div>
    </div>
  {% endif %}
</div>
{% endfor %}
</body>
</html>""")

def _inject_cover_date(content: str) -> str:
    """Replace cover date placeholder with current Month Year."""
    formatted = datetime.utcnow().strftime("%B %Y")
    if "[DATE]" in content:
        return content.replace("[DATE]", formatted)
    return content


def _strip_cover_brand_line(md_text: str) -> str:
    """Remove the InfinityCapital text line for PPTX cover rendering."""
    lines = [
        line for line in md_text.splitlines()
        if line.strip().lower() != "infinitycapital"
    ]
    return "\n".join(lines).strip()


def _strip_code_fences(md_text: str) -> str:
    """Remove markdown code fence wrappers like ```markdown ... ```."""
    text = md_text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
    if text.rstrip().endswith("```"):
        text = text.rstrip()[:-3].rstrip()
    return text


def _extract_cover_lines(md_text: str) -> tuple[str, str]:
    """Extract date line and title line from cover markdown."""
    md_text = _strip_code_fences(md_text)
    lines = [line.strip() for line in md_text.splitlines() if line.strip()]
    if not lines:
        return "", ""
    date_line = lines[0]
    title_line = lines[1] if len(lines) > 1 else ""
    for prefix in ("### ", "## ", "# "):
        if title_line.startswith(prefix):
            title_line = title_line[len(prefix):]
            break
    return date_line, title_line


def _svg_to_png_bytes(svg: str, height_px: int = 50) -> bytes | None:
    """Convert an SVG string to PNG bytes for PPTX rendering."""
    try:
        import cairosvg  # type: ignore
    except Exception as e:
        logger.warning("cairosvg not available for SVG conversion: %s", e)
        return None
    try:
        return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_height=height_px)
    except Exception as e:
        logger.warning("Failed to convert SVG to PNG: %s", e)
        return None


async def assemble_report(
    state: dict,
    load_artifact_fn=None,
) -> dict:
    """Assemble all slide outputs into PPTX and PDF bytes.

    Args:
        state: Session state dict containing slide_NN_content and
               slide_NN_chart_image keys.
        load_artifact_fn: Async callable(filename) -> bytes|None for
                          loading chart image artifacts.

    Returns:
        Dict with status, slides_generated, pptx_bytes, pdf_bytes.
    """
    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT

    pdf_sections = []
    slides_generated = 0

    for spec in SLIDE_REGISTRY:
        content = state.get(slide_content_key(spec.slide_number), "")
        if not content:
            continue
        if spec.slide_number == 1:
            content = _inject_cover_date(content)
        pptx_content = content
        cover_logo_png = None
        infinity_logo_png = None
        cover_date_line = ""
        cover_title_line = ""
        if spec.slide_number == 1:
            pptx_content = _strip_cover_brand_line(content)
            cover_logo_png = _svg_to_png_bytes(INFINITY_TEXT_LOGO_SVG)
            if INFINITY_LOGO_PNG_BYTES:
                infinity_logo_png = INFINITY_LOGO_PNG_BYTES
            cover_date_line, cover_title_line = _extract_cover_lines(pptx_content)

        # --- Build PPTX slide ---
        slide_layout = prs.slide_layouts[6]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)
        if spec.slide_number != 1:
            add_title_bar(slide, spec.title)

        # Load chart image if this slide has one
        chart_filename = state.get(
            slide_chart_image_key(spec.slide_number), ""
        )
        chart_bytes = None
        if chart_filename and load_artifact_fn:
            chart_bytes = await load_artifact_fn(chart_filename)

        roadmap_continuations = []
        if spec.slide_type == SlideType.ROADMAP and load_artifact_fn:
            for p in range(2, 15):
                key = f"slide_{spec.slide_number:02d}_chart_image_{p}"
                fn = state.get(key, "")
                if fn:
                    b = await load_artifact_fn(fn)
                    if b:
                        roadmap_continuations.append(b)
                    else:
                        break
                else:
                    break

        remaining = ""
        if spec.slide_number == 1:
            date_y = Inches(0.7)
            logo_y = SLIDE_HEIGHT - Inches(0.9)
            title_height = Inches(0.6)
            title_y = int((date_y + logo_y - title_height) / 2)

            date_box = slide.shapes.add_textbox(
                CONTENT_LEFT, date_y, Inches(6.5), Inches(0.4)
            )
            date_tf = date_box.text_frame
            date_tf.text = cover_date_line.upper() if cover_date_line else ""
            date_tf.paragraphs[0].font.size = Pt(12)
            date_tf.paragraphs[0].font.color.rgb = TEXT_COLOR
            date_tf.paragraphs[0].font.name = "Arial"

            title_box = slide.shapes.add_textbox(
                CONTENT_LEFT, title_y, Inches(10.5), title_height
            )
            title_tf = title_box.text_frame
            title_tf.text = cover_title_line
            title_tf.paragraphs[0].font.size = Pt(21)
            title_tf.paragraphs[0].font.bold = True
            title_tf.paragraphs[0].font.color.rgb = ACCENT_COLOR
            title_tf.paragraphs[0].font.name = "Arial"
        elif spec.slide_type == SlideType.CHART and chart_bytes:
            img_stream = io.BytesIO(chart_bytes)
            slide.shapes.add_picture(
                img_stream,
                CONTENT_LEFT,
                CONTENT_TOP,
                CONTENT_WIDTH,
                Inches(4.5),
            )
            remaining = render_markdown_to_textbox(
                slide, pptx_content,
                left=CONTENT_LEFT, top=Inches(5.8),
                width=CONTENT_WIDTH, height=Inches(1.2),
            )
        elif spec.slide_type == SlideType.ROADMAP and chart_bytes:
            img_stream = io.BytesIO(chart_bytes)
            slide.shapes.add_picture(
                img_stream,
                CONTENT_LEFT,
                CONTENT_TOP,
                CONTENT_WIDTH,
                Inches(5.8),
            )
            remaining = render_markdown_to_textbox(
                slide, content,
                left=CONTENT_LEFT, top=Inches(6.2),
                width=CONTENT_WIDTH, height=Inches(0.8),
            )
        elif spec.slide_type == SlideType.MIXED and chart_bytes:
            remaining = render_markdown_to_textbox(
                slide, pptx_content,
                left=CONTENT_LEFT, top=CONTENT_TOP,
                width=Inches(5.5), height=CONTENT_HEIGHT,
            )
            img_stream = io.BytesIO(chart_bytes)
            slide.shapes.add_picture(
                img_stream,
                Inches(6.75), CONTENT_TOP,
                Inches(5.8), Inches(4.0),
            )
        else:
            remaining = render_markdown_to_textbox(slide, pptx_content)

        if spec.slide_number == 1 and cover_logo_png:
            slide.shapes.add_picture(
                io.BytesIO(cover_logo_png),
                CONTENT_LEFT,
                SLIDE_HEIGHT - Inches(0.9),
                height=Inches(0.45),
            )
        if spec.slide_number == 1 and infinity_logo_png:
            logo_height = Inches(1.4)
            logo_margin = Inches(0.4)
            logo_shape = slide.shapes.add_picture(
                io.BytesIO(infinity_logo_png),
                Inches(0),
                Inches(0),
                height=logo_height,
            )
            logo_shape.left = int(SLIDE_WIDTH - logo_shape.width - logo_margin)
            logo_shape.top = int(SLIDE_HEIGHT - logo_shape.height - logo_margin)

        # FINAL TITLE FIX: Ensure title bar on all content slides is Pt 24 White
        if spec.slide_number != 1:
            for s in slide.shapes:
                # Identification: wide rectangle at the very top
                if s.top < Inches(0.1) and s.width > Inches(10) and hasattr(s, "text_frame"):
                    for p in s.text_frame.paragraphs:
                        p.font.size = Pt(24)
                        p.font.color.rgb = WHITE
                        p.font.bold = True

        # Create continuation slides for overflow content
        while remaining:
            cont_slide = prs.slides.add_slide(slide_layout)
            add_title_bar(cont_slide, spec.title + " (cont.)")
            remaining = render_markdown_to_textbox(cont_slide, remaining)

        # Roadmap continuation pages (one PPTX slide per extra chart image)
        for cont_bytes in roadmap_continuations:
            cont_slide = prs.slides.add_slide(slide_layout)
            add_title_bar(cont_slide, spec.title + " (cont.)")
            img_stream = io.BytesIO(cont_bytes)
            cont_slide.shapes.add_picture(
                img_stream,
                CONTENT_LEFT,
                CONTENT_TOP,
                CONTENT_WIDTH,
                Inches(5.8),
            )
            for s in cont_slide.shapes:
                if s.top < Inches(0.1) and s.width > Inches(10) and hasattr(s, "text_frame"):
                    for p in s.text_frame.paragraphs:
                        p.font.size = Pt(24)
                        p.font.color.rgb = WHITE
                        p.font.bold = True
                    break

        # --- Build PDF section ---
        # Strip fenced wrappers (e.g. ```markdown ... ```) so inner content is rendered.
        # Otherwise the whole response is output as a code block and tables stay raw.
        raw_for_pdf = _strip_code_fences(content)
        html_content = md_lib.markdown(
            raw_for_pdf,
            extensions=["tables", "fenced_code"],
        )

        chart_img_b64 = None
        if chart_bytes:
            chart_img_b64 = base64.b64encode(chart_bytes).decode("utf-8")

        cover_date = ""
        cover_title = ""
        if spec.slide_number == 1:
            cover_date, cover_title = _extract_cover_lines(content)

        pdf_sections.append({
            "slide_number": spec.slide_number,
            "title": spec.title,
            "html_content": html_content,
            "chart_img": chart_img_b64,
            "is_cover": spec.slide_number == 1,
            "cover_logo_svg": INFINITY_TEXT_LOGO_SVG if spec.slide_number == 1 else "",
            "infinity_logo_png": INFINITY_LOGO_PNG_B64 if spec.slide_number == 1 else "",
            "cover_date": cover_date,
            "cover_title": cover_title,
        })
        # Roadmap continuation pages in PDF (one page per extra chart image)
        for cont_bytes in roadmap_continuations:
            pdf_sections.append({
                "slide_number": spec.slide_number,
                "title": spec.title + " (cont.)",
                "html_content": "",
                "chart_img": base64.b64encode(cont_bytes).decode("utf-8"),
                "is_cover": False,
                "cover_logo_svg": "",
                "infinity_logo_png": "",
                "cover_date": "",
                "cover_title": "",
            })

        slides_generated += 1

    # --- Generate bytes ---
    pptx_buf = io.BytesIO()
    prs.save(pptx_buf)
    pptx_bytes = pptx_buf.getvalue()

    html_str = PDF_TEMPLATE.render(sections=pdf_sections)
    pdf_bytes = HTML(string=html_str).write_pdf()

    return {
        "status": "success",
        "slides_generated": slides_generated,
        "pptx_bytes": pptx_bytes,
        "pdf_bytes": pdf_bytes,
    }

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
    ACCENT_COLOR,
    TEXT_COLOR,
    add_title_bar,
    render_markdown_to_textbox,
)
from report_agents.utils.state_keys import slide_content_key, slide_chart_image_key

logger = logging.getLogger(__name__)


# PDF HTML template
COVER_LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="-5 -15 830 150" height="50"><g transform="matrix(0.635,0,0,0.635,-213.63,-268.16)"><g opacity="1" transform="matrix(1,0,0,1,443.831,531.449)"><path fill="#282828" d="M12.651,-60.065C-3.306,-60.065-14.019,-53.454-21.997,-40.917L-22.681,-40.917L-22.681,-56.874L-53,-56.874L-53,60.065L-21.997,60.065L-21.997,-6.269C-21.997,-22.226-11.967,-33.167,1.71,-33.167C14.703,-33.167,21.998,-24.277,21.998,-11.74L21.998,60.065L53,60.065L53,-16.299C53,-41.829,36.814,-60.065,12.651,-60.065z"/></g><g opacity="1" transform="matrix(1,0,0,1,534.439,509.852)"><path fill="#282828" d="M-18.008,-45.762L-18.008,-35.276L-33.965,-35.276L-33.965,-13.849L-18.008,-13.849L-18.008,81.663L12.993,81.663L12.993,-13.849L33.965,-13.849L33.965,-35.276L12.993,-35.276L12.993,-43.938C12.993,-56.02,19.376,-57.843,33.965,-57.159L33.965,-81.094C4.103,-84.285,-18.008,-74.256,-18.008,-45.762z"/></g><g opacity="1" transform="matrix(1,0,0,1,597.81,533.045)"><path fill="#282828" d="M-15.501,58.469L15.501,58.469L15.501,-58.469L-15.501,-58.469z"/></g><g opacity="1" transform="matrix(1,0,0,1,597.81,442.435)"><path fill="#282828" d="M-15.501,13.905L15.501,13.905L15.501,-13.905L-15.501,-13.905z"/></g><g opacity="1" transform="matrix(1,0,0,1,679.524,531.449)"><path fill="#282828" d="M12.651,-60.065C-3.306,-60.065-14.019,-53.454-21.997,-40.917L-22.681,-40.917L-22.681,-56.874L-53,-56.874L-53,60.065L-21.997,60.065L-21.997,-6.269C-21.997,-22.226-11.967,-33.167,1.71,-33.167C14.703,-33.167,21.998,-24.277,21.998,-11.74L21.998,60.065L53,60.065L53,-16.299C53,-41.829,36.814,-60.065,12.651,-60.065z"/></g><g opacity="1" transform="matrix(1,0,0,1,760.328,533.045)"><path fill="#282828" d="M-15.501,58.469L15.501,58.469L15.501,-58.469L-15.501,-58.469z"/></g><g opacity="1" transform="matrix(1,0,0,1,760.328,442.435)"><path fill="#282828" d="M-15.501,13.905L15.501,13.905L15.501,-13.905L-15.501,-13.905z"/></g><g opacity="1" transform="matrix(1,0,0,1,815.832,514.923)"><path fill="#282828" d="M12.879,42.171L12.879,-19.832L32.939,-19.832L32.939,-40.347L12.879,-40.347L12.879,-76.819L-17.438,-76.819L-17.438,-40.347L-33.623,-40.347L-33.623,-19.832L-17.438,-19.832L-17.438,48.782C-17.438,70.893-0.799,76.819,14.247,76.819C26.557,76.819,33.623,76.364,33.623,76.364L33.623,53.569L28.38,53.797C24.505,53.797,12.879,50.833,12.879,42.171z"/></g><g opacity="1" transform="matrix(1,0,0,1,906.779,552.193)"><path fill="#282828" d="M24.96,-77.617L8.548,-24.961C4.901,-14.247,1.709,0.571,1.709,0.571L1.253,0.571C1.253,0.571-2.622,-14.247-6.269,-24.961L-23.594,-77.617L-56.19,-77.617L-24.733,5.584C-18.122,23.365-15.843,30.887-15.843,37.27C-15.843,46.844-20.858,53.227-33.167,53.227L-44.109,53.227L-44.109,77.617L-25.873,77.617C-2.166,77.617,6.496,68.271,15.386,42.285L56.19,-77.617z"/></g><g transform="matrix(1,0,0,1,1.25,0)"><g opacity="1" transform="matrix(1,0,0,1,1034.995,510.136)"><path fill="#282828" d="M5.472,57.672C-21.882,57.672-39.207,33.737-39.207,0.456C-39.207,-31.913-24.847,-56.988,5.243,-56.988C24.391,-56.988,36.7,-46.275,39.664,-29.862L72.489,-29.862C69.069,-60.863,45.362,-84.798,5.243,-84.798C-42.855,-84.798-72.944,-47.869-72.944,0.456C-72.944,49.466-40.346,84.798,5.472,84.798C28.038,84.798,43.767,77.959,54.937,67.473C65.878,57.215,72.033,43.311,72.944,28.95L40.575,28.95C38.524,46.046,24.847,57.672,5.472,57.672z"/></g><g opacity="1" transform="matrix(1,0,0,1,1164.58,532.931)"><path fill="#282828" d="M50.491,41.259L50.491,-18.236C50.491,-45.59,36.358,-61.319,1.254,-61.319C-32.939,-61.319-48.212,-43.311-49.124,-22.795L-21.542,-22.795C-20.63,-33.965-13.563,-39.208,1.026,-39.208C14.019,-39.208,20.629,-33.737,20.629,-25.303C20.629,-16.413,11.74,-14.817-7.636,-12.082C-33.622,-8.435-54.594,-0.228-54.594,25.531C-54.594,48.782-37.727,61.319-13.791,61.319C6.268,61.319,14.703,54.481,20.629,45.59L21.085,45.59C21.77,50.832,22.909,56.304,24.733,58.583L54.594,58.583L54.594,57.444C51.859,55.392,50.491,50.149,50.491,41.259zM21.313,17.325C21.313,28.721,11.512,39.664-6.269,39.664C-17.21,39.664-24.505,35.788-24.505,24.846C-24.505,13.905-16.527,10.258-0.341,6.611C7.409,4.787,15.842,2.963,21.313,-0.228z"/></g><g opacity="1" transform="matrix(1,0,0,1,1285.729,550.597)"><path fill="#282828" d="M7.066,-79.213C-8.89,-79.213-19.832,-71.691-27.354,-61.433L-28.038,-61.433L-28.038,-76.022L-57.899,-76.022L-57.899,79.213L-26.898,79.213L-26.898,27.696L-26.442,27.696C-19.832,37.726-9.118,44.336,7.294,44.336C37.384,44.336,57.899,20.402,57.899,-17.438C57.899,-53.91,38.067,-79.213,7.066,-79.213zM0.684,18.578C-17.78,18.578-27.583,4.673-27.583,-16.527C-27.583,-37.498-19.832,-54.138-0.456,-54.138C18.692,-54.138,26.442,-38.638,26.442,-16.527C26.442,5.584,16.413,18.578,0.684,18.578z"/></g><g opacity="1" transform="matrix(1,0,0,1,1366.647,442.435)"><path fill="#282828" d="M-15.501,13.905L15.501,13.905L15.501,-13.905L-15.501,-13.905z"/></g><g opacity="1" transform="matrix(1,0,0,1,1366.647,533.045)"><path fill="#282828" d="M-15.501,58.469L15.501,58.469L15.501,-58.469L-15.501,-58.469z"/></g><g opacity="1" transform="matrix(1,0,0,1,1422.152,514.923)"><path fill="#282828" d="M12.879,42.171L12.879,-19.832L32.938,-19.832L32.938,-40.347L12.879,-40.347L12.879,-76.819L-17.438,-76.819L-17.438,-40.347L-33.623,-40.347L-33.623,-19.832L-17.438,-19.832L-17.438,48.782C-17.438,70.893-0.799,76.819,14.246,76.819C26.557,76.819,33.623,76.364,33.623,76.364L33.623,53.569L28.379,53.797C24.504,53.797,12.879,50.833,12.879,42.171z"/></g><g opacity="1" transform="matrix(1,0,0,1,1514.236,532.931)"><path fill="#282828" d="M50.491,41.259L50.491,-18.236C50.491,-45.59,36.358,-61.319,1.254,-61.319C-32.939,-61.319-48.211,-43.311-49.123,-22.795L-21.541,-22.795C-20.629,-33.965-13.563,-39.208,1.025,-39.208C14.019,-39.208,20.629,-33.737,20.629,-25.303C20.629,-16.413,11.74,-14.817-7.637,-12.082C-33.623,-8.435-54.594,-0.228-54.594,25.531C-54.594,48.782-37.727,61.319-13.791,61.319C6.269,61.319,14.703,54.481,20.629,45.59L21.086,45.59C21.77,50.832,22.909,56.304,24.732,58.583L54.594,58.583L54.594,57.444C51.86,55.392,50.491,50.149,50.491,41.259zM21.313,17.325C21.313,28.721,11.511,39.664-6.269,39.664C-17.211,39.664-24.505,35.788-24.505,24.846C-24.505,13.905-16.527,10.258-0.342,6.611C7.408,4.787,15.842,2.963,21.313,-0.228z"/></g></g></g><g transform="matrix(0.637,0,0,0.637,-214.83,-269.49)"><g opacity="1" transform="matrix(1,0,0,1,358.353,510.022)"><path fill="#282828" d="M-16.527,81.492L16.527,81.492L16.527,-81.492L-16.527,-81.492z"/></g></g><g transform="matrix(0.637,0,0,0.637,-218.80,-269.46)"><g opacity="1" transform="matrix(1,0,0,1,1596.749,510.022)"><path fill="#282828" d="M-16.527,-81.492L-16.527,81.492L16.527,81.492L16.527,-81.492z"/></g></g></svg>"""
ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
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
  @page { size: landscape; margin: 0.75in; }
  :root {
    --ink: #111111;
    --muted: #7a7a7a;
    --accent: #A89968;
    --bar: #5b5b5b;
    --light: #f2f2f2;
    --grid: #e5e5e5;
  }
  body { font-family: Arial, Helvetica, sans-serif; color: var(--ink); line-height: 1.4; }
  .slide { page-break-after: always; padding: 0; position: relative; }
  .slide:last-child { page-break-after: avoid; }
  .content { font-size: 12pt; }
  p { margin: 0 0 10px 0; }
  ul { margin: 0 0 12px 18px; }
  li { margin: 4px 0; }
  blockquote {
    margin: 10px 0; padding: 8px 12px; background: var(--light);
    border-left: 4px solid var(--bar);
  }
  table { border-collapse: collapse; width: 100%; margin: 10px 0 14px 0; }
  th, td { border: 1px solid var(--grid); padding: 8px 10px; font-size: 10.5pt; }
  th { background: var(--bar); color: #ffffff; text-align: center; }
  td { text-align: right; }
  td:first-child, th:first-child { text-align: left; }
  tr:nth-child(even) { background: #fafafa; }
  img { max-width: 92%; height: auto; display: block; margin: 10px auto; }
  h2 { font-size: 22pt; font-weight: 800; margin: 6px 0 8px 0; }
  h3 {
    font-size: 13.5pt; font-weight: 700; color: #ffffff;
    background: var(--bar); padding: 6px 10px; margin: 12px 0 8px 0;
  }

  /* Cover layout */
  .cover .content { padding: 0; }
  .cover-stack {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 6.5in;
  }
  .cover-date {
    color: var(--ink); font-size: 12pt; letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .cover-title {
    color: var(--accent); font-size: 21pt; font-weight: 400;
    letter-spacing: 0.04em;
  }
  .cover-branding { }
  .cover-branding svg { height: 50px; width: auto; display: block; }
  .cover-infinity-logo {
    position: absolute;
    right: 0;
    bottom: 0;
    height: 70px;
    width: auto;
    display: block;
    max-width: none;
    margin: 0;
  }
</style>
</head>
<body>
{% for section in sections %}
<div class="slide{% if section.is_cover %} cover{% endif %}">
  <div class="content">
    {% if section.is_cover %}
    <div class="cover-stack">
      <div class="cover-date">{{ section.cover_date }}</div>
      <div class="cover-title">{{ section.cover_title }}</div>
      {% if section.cover_logo_svg %}
      <div class="cover-branding">{{ section.cover_logo_svg }}</div>
      {% endif %}
    </div>
    {% if section.infinity_logo_png %}
    <img class="cover-infinity-logo"
         src="data:image/png;base64,{{ section.infinity_logo_png }}"
         alt="Infinity logo"/>
    {% endif %}
    {% else %}
    {{ section.html_content }}
    {% endif %}
  </div>
  {% if section.chart_img %}
  <img src="data:image/png;base64,{{ section.chart_img }}" alt="Chart"/>
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
            cover_logo_png = _svg_to_png_bytes(COVER_LOGO_SVG)
            if INFINITY_LOGO_PNG_BYTES:
                infinity_logo_png = INFINITY_LOGO_PNG_BYTES
            cover_date_line, cover_title_line = _extract_cover_lines(pptx_content)

        # --- Build PPTX slide ---
        slide_layout = prs.slide_layouts[6]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)

        # Load chart image if this slide has one
        chart_filename = state.get(
            slide_chart_image_key(spec.slide_number), ""
        )
        chart_bytes = None
        if chart_filename and load_artifact_fn:
            chart_bytes = await load_artifact_fn(chart_filename)

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
            title_tf.paragraphs[0].font.bold = False
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

        # Create continuation slides for overflow content
        while remaining:
            cont_slide = prs.slides.add_slide(slide_layout)
            add_title_bar(cont_slide, spec.title + " (cont.)")
            remaining = render_markdown_to_textbox(cont_slide, remaining)

        # --- Build PDF section ---
        html_content = md_lib.markdown(
            content,
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
            "title": spec.title,
            "html_content": html_content,
            "chart_img": chart_img_b64,
            "is_cover": spec.slide_number == 1,
            "cover_logo_svg": COVER_LOGO_SVG if spec.slide_number == 1 else "",
            "infinity_logo_png": INFINITY_LOGO_PNG_B64 if spec.slide_number == 1 else "",
            "cover_date": cover_date,
            "cover_title": cover_title,
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

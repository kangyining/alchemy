"""Report assembly: builds PPTX and PDF from slide agent outputs."""

import base64
import io
import json

import markdown as md_lib
from jinja2 import Template
from pptx import Presentation
from pptx.util import Inches
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
    add_title_bar,
    render_markdown_to_textbox,
)
from report_agents.utils.state_keys import slide_content_key, slide_chart_image_key


# PDF HTML template
PDF_TEMPLATE = Template("""<!DOCTYPE html>
<html>
<head>
<style>
  @page { size: landscape; margin: 0.75in; }
  body { font-family: Arial, Helvetica, sans-serif; color: #333; line-height: 1.5; }
  .slide { page-break-after: always; padding: 1em 0; }
  .slide:last-child { page-break-after: avoid; }
  .slide-title {
    color: #1A3C6E; font-size: 22pt; font-weight: bold;
    border-bottom: 3px solid #2E86AB; padding-bottom: 8px; margin-bottom: 16px;
  }
  table { border-collapse: collapse; width: 100%; margin: 1em 0; }
  th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: right; }
  th { background: #1A3C6E; color: white; text-align: center; }
  tr:nth-child(even) { background: #f9f9f9; }
  td:first-child, th:first-child { text-align: left; }
  img { max-width: 90%; height: auto; display: block; margin: 1em auto; }
  h2 { color: #1A3C6E; }
  h3 { color: #2E86AB; }
  ul { margin-left: 1.5em; }
</style>
</head>
<body>
{% for section in sections %}
<div class="slide">
  <div class="slide-title">{{ section.title }}</div>
  {{ section.html_content }}
  {% if section.chart_img %}
  <img src="data:image/png;base64,{{ section.chart_img }}" alt="Chart"/>
  {% endif %}
</div>
{% endfor %}
</body>
</html>""")


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

        # --- Build PPTX slide ---
        slide_layout = prs.slide_layouts[6]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)
        add_title_bar(slide, spec.title)

        # Load chart image if this slide has one
        chart_filename = state.get(
            slide_chart_image_key(spec.slide_number), ""
        )
        chart_bytes = None
        if chart_filename and load_artifact_fn:
            chart_bytes = await load_artifact_fn(chart_filename)

        if spec.slide_type == SlideType.CHART and chart_bytes:
            img_stream = io.BytesIO(chart_bytes)
            slide.shapes.add_picture(
                img_stream,
                CONTENT_LEFT,
                CONTENT_TOP,
                CONTENT_WIDTH,
                Inches(4.5),
            )
            render_markdown_to_textbox(
                slide, content,
                left=CONTENT_LEFT, top=Inches(5.8),
                width=CONTENT_WIDTH, height=Inches(1.2),
            )
        elif spec.slide_type == SlideType.MIXED and chart_bytes:
            render_markdown_to_textbox(
                slide, content,
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
            render_markdown_to_textbox(slide, content)

        # --- Build PDF section ---
        html_content = md_lib.markdown(
            content,
            extensions=["tables", "fenced_code"],
        )
        chart_img_b64 = None
        if chart_bytes:
            chart_img_b64 = base64.b64encode(chart_bytes).decode("utf-8")

        pdf_sections.append({
            "title": spec.title,
            "html_content": html_content,
            "chart_img": chart_img_b64,
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

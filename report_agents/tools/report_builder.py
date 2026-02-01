"""Report assembly tool: builds PPTX and PDF from slide agent outputs."""

import io
import json

import markdown as md_lib
from jinja2 import Template
from pptx import Presentation
from pptx.util import Inches
from weasyprint import HTML

from google.adk.tools import ToolContext
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


def _load_chart_image(tool_context: ToolContext, filename: str) -> bytes | None:
    """Load a chart image artifact, return raw bytes or None."""
    try:
        artifact = tool_context.load_artifact(filename)
        if artifact and artifact.inline_data:
            return artifact.inline_data.data
    except Exception:
        pass
    return None


def assemble_report(tool_context: ToolContext) -> dict:
    """Assemble all slide outputs into PPTX and PDF files.

    Reads slide content from session state, builds a PowerPoint presentation
    and a PDF document. Saves both as ADK artifacts for download.

    Returns:
        Status dict with slide count and artifact names.
    """
    import base64

    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT

    pdf_sections = []
    slides_generated = 0

    for spec in SLIDE_REGISTRY:
        content = tool_context.state.get(slide_content_key(spec.slide_number), "")
        if not content:
            continue

        # --- Build PPTX slide ---
        slide_layout = prs.slide_layouts[6]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)
        add_title_bar(slide, spec.title)

        # Load chart image if this slide has one
        chart_filename = tool_context.state.get(
            slide_chart_image_key(spec.slide_number), ""
        )
        chart_bytes = None
        if chart_filename:
            chart_bytes = _load_chart_image(tool_context, chart_filename)

        if spec.slide_type == SlideType.CHART and chart_bytes:
            # Chart-only slide: image takes most of the space, small text below
            img_stream = io.BytesIO(chart_bytes)
            slide.shapes.add_picture(
                img_stream,
                CONTENT_LEFT,
                CONTENT_TOP,
                CONTENT_WIDTH,
                Inches(4.5),
            )
            # Add summary text below chart
            render_markdown_to_textbox(
                slide, content,
                left=CONTENT_LEFT, top=Inches(5.8),
                width=CONTENT_WIDTH, height=Inches(1.2),
            )
        elif spec.slide_type == SlideType.MIXED and chart_bytes:
            # Mixed: text on left, chart on right
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
            # Text or table slide
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

    # --- Save PPTX artifact ---
    pptx_buf = io.BytesIO()
    prs.save(pptx_buf)
    pptx_buf.seek(0)
    tool_context.save_artifact(
        "financial_report.pptx",
        genai_types.Part.from_data(
            data=pptx_buf.read(),
            mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
    )

    # --- Generate and save PDF artifact ---
    html_str = PDF_TEMPLATE.render(sections=pdf_sections)
    pdf_bytes = HTML(string=html_str).write_pdf()
    tool_context.save_artifact(
        "financial_report.pdf",
        genai_types.Part.from_data(
            data=pdf_bytes,
            mime_type="application/pdf",
        ),
    )

    return {
        "status": "success",
        "slides_generated": slides_generated,
        "artifacts": ["financial_report.pptx", "financial_report.pdf"],
    }

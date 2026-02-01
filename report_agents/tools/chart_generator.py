"""Chart generation tools: Gemini image gen first, matplotlib fallback."""

import io
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from google import genai
from google.adk.tools import ToolContext
from google.genai import types as genai_types

CHART_STYLE_PROMPT = """Professional financial report chart. Clean, modern design.
Dark navy (#1A3C6E) for titles, blue (#2E86AB) as primary color, white background.
Sans-serif font (Arial or Helvetica). Clear axis labels with units.
Value labels displayed on each data point. No gridlines clutter.
High resolution, presentation-ready. 16:9 aspect ratio."""

# Matplotlib style config matching the Gemini prompt
MPL_COLORS = [
    "#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#3B1F2B",
    "#44BBA4", "#E94F37", "#393E41",
]
MPL_STYLE = {
    "font.family": "sans-serif",
    "axes.facecolor": "#FFFFFF",
    "figure.facecolor": "#FFFFFF",
    "axes.titlesize": 16,
    "axes.titleweight": "bold",
    "axes.labelsize": 12,
}
plt.rcParams.update(MPL_STYLE)


def _get_genai_client():
    """Create a Gemini client using Vertex AI (ADC) or API key."""
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE":
        return genai.Client(
            vertexai=True,
            project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
            location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
        )
    return genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))


def _extract_image_bytes(response) -> bytes | None:
    """Extract image bytes from a Gemini response."""
    if response and response.candidates:
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                return part.inline_data.data
    return None


def _validate_chart_numbers(client, image_bytes: bytes, source_data: dict) -> bool:
    """Ask Gemini to read the chart image and verify numbers match source data."""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=[
                genai_types.Part.from_data(data=image_bytes, mime_type="image/png"),
                (
                    "Read all numeric values visible in this chart. "
                    "Return them as a JSON object with key 'values' containing a list of numbers. "
                    "Only return the JSON, nothing else."
                ),
            ],
        )
        # Extract the JSON from response
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        extracted = json.loads(text)
        extracted_values = set()
        for v in extracted.get("values", []):
            if isinstance(v, (int, float)):
                extracted_values.add(round(float(v), 1))

        # Check that all source values appear in the extracted values
        source_values = {round(float(v), 1) for v in source_data.get("values", [])}
        # Allow 10% tolerance per value
        for sv in source_values:
            found = any(abs(ev - sv) <= abs(sv) * 0.1 + 0.5 for ev in extracted_values)
            if not found:
                return False
        return True
    except Exception:
        return False


def _save_chart_artifact(tool_context: ToolContext, slide_number: int, image_bytes: bytes):
    """Save chart image as ADK artifact and store reference in state."""
    filename = f"slide_{slide_number:02d}_chart.png"
    artifact = genai_types.Part.from_data(data=image_bytes, mime_type="image/png")
    tool_context.save_artifact(filename, artifact)
    tool_context.state[f"slide_{slide_number:02d}_chart_image"] = filename


# --- Matplotlib fallback renderers ---

def _render_matplotlib_bar_chart(data: dict) -> bytes:
    """Render a bar chart with matplotlib, return PNG bytes."""
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(data["categories"], data["values"], color=MPL_COLORS[0])
    ax.set_title(data.get("title", ""), fontsize=16, fontweight="bold", color="#1A3C6E")
    ax.set_xlabel(data.get("x_label", ""), fontsize=12)
    ax.set_ylabel(data.get("y_label", ""), fontsize=12)
    fmt = data.get("value_format", "{:,.1f}")
    for bar, val in zip(bars, data["values"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            bar.get_height(),
            fmt.format(val),
            ha="center", va="bottom", fontsize=10,
        )
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _render_matplotlib_line_chart(data: dict) -> bytes:
    """Render a line chart with matplotlib, return PNG bytes."""
    fig, ax = plt.subplots(figsize=(10, 6))
    for i, series in enumerate(data.get("series", [{"values": data.get("values", [])}])):
        label = series.get("label", "")
        values = series["values"]
        ax.plot(
            data["categories"], values,
            marker="o", color=MPL_COLORS[i % len(MPL_COLORS)], label=label, linewidth=2,
        )
        fmt = data.get("value_format", "{:,.1f}")
        for x, y in zip(data["categories"], values):
            ax.annotate(fmt.format(y), (x, y), textcoords="offset points", xytext=(0, 10), ha="center", fontsize=9)
    ax.set_title(data.get("title", ""), fontsize=16, fontweight="bold", color="#1A3C6E")
    ax.set_xlabel(data.get("x_label", ""), fontsize=12)
    ax.set_ylabel(data.get("y_label", ""), fontsize=12)
    if any(s.get("label") for s in data.get("series", [])):
        ax.legend()
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _render_matplotlib_pie_chart(data: dict) -> bytes:
    """Render a pie chart with matplotlib, return PNG bytes."""
    fig, ax = plt.subplots(figsize=(8, 8))
    colors = MPL_COLORS[: len(data["categories"])]
    wedges, texts, autotexts = ax.pie(
        data["values"], labels=data["categories"], colors=colors,
        autopct="%1.1f%%", startangle=90, textprops={"fontsize": 11},
    )
    ax.set_title(data.get("title", ""), fontsize=16, fontweight="bold", color="#1A3C6E")
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


MPL_RENDERERS = {
    "bar": _render_matplotlib_bar_chart,
    "line": _render_matplotlib_line_chart,
    "pie": _render_matplotlib_pie_chart,
}


# --- ADK Tool Functions ---

def _generate_chart(
    chart_type: str, data_json: str, slide_number: int, tool_context: ToolContext
) -> dict:
    """Shared chart generation logic: Gemini first, matplotlib fallback."""
    data = json.loads(data_json)

    # Step 1: Try Gemini image generation
    try:
        client = _get_genai_client()
        type_desc = {"bar": "bar chart", "line": "line chart", "pie": "pie chart"}.get(chart_type, "chart")

        values_desc = "\n".join(
            f"  - {c}: {v}" for c, v in zip(data["categories"], data["values"])
        )
        prompt = f"""{CHART_STYLE_PROMPT}
Create a {type_desc} with title: "{data.get('title', '')}"
X-axis label: "{data.get('x_label', '')}", Y-axis label: "{data.get('y_label', '')}"
Categories and exact values (render these numbers precisely on the chart):
{values_desc}
"""
        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=prompt,
            config=genai_types.GenerateContentConfig(response_modalities=["Image"]),
        )
        image_bytes = _extract_image_bytes(response)

        if image_bytes and _validate_chart_numbers(client, image_bytes, data):
            _save_chart_artifact(tool_context, slide_number, image_bytes)
            return {"status": "success", "method": "gemini_image_gen", "chart_type": chart_type}
    except Exception:
        pass

    # Step 2: Fallback to matplotlib
    renderer = MPL_RENDERERS.get(chart_type, _render_matplotlib_bar_chart)
    image_bytes = renderer(data)
    _save_chart_artifact(tool_context, slide_number, image_bytes)
    return {"status": "success", "method": "matplotlib_fallback", "chart_type": chart_type}


def generate_bar_chart(data_json: str, slide_number: int, tool_context: ToolContext) -> dict:
    """Generate a bar chart from structured data.

    Args:
        data_json: JSON string with keys: categories (list[str]), values (list[float]),
                   title (str), x_label (str), y_label (str), value_format (str, optional)
        slide_number: The slide number this chart belongs to.

    Returns:
        Status dict with generation method used.
    """
    return _generate_chart("bar", data_json, slide_number, tool_context)


def generate_line_chart(data_json: str, slide_number: int, tool_context: ToolContext) -> dict:
    """Generate a line chart from structured data.

    Args:
        data_json: JSON string with keys: categories (list[str]), values (list[float]),
                   title (str), x_label (str), y_label (str),
                   series (list[dict] with 'label' and 'values', optional)
        slide_number: The slide number this chart belongs to.

    Returns:
        Status dict with generation method used.
    """
    return _generate_chart("line", data_json, slide_number, tool_context)


def generate_pie_chart(data_json: str, slide_number: int, tool_context: ToolContext) -> dict:
    """Generate a pie chart from structured data.

    Args:
        data_json: JSON string with keys: categories (list[str]), values (list[float]),
                   title (str)
        slide_number: The slide number this chart belongs to.

    Returns:
        Status dict with generation method used.
    """
    return _generate_chart("pie", data_json, slide_number, tool_context)

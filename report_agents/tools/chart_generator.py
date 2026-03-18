"""Chart generation tools: Gemini image gen first, matplotlib fallback."""

import io
import json
import logging
import os
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Suppress matplotlib categorical units messages (logged at INFO level)
logging.getLogger("matplotlib.category").setLevel(logging.WARNING)
from matplotlib.patches import FancyBboxPatch

from google import genai
from google.adk.tools import ToolContext
from google.genai import types as genai_types

from report_agents.utils.gemini_models import GEMINI_PRO_MODEL, GEMINI_IMAGE_MODEL

logger = logging.getLogger(__name__)

CHART_STYLE_PROMPT = """Professional financial report chart. Clean, modern design.
Dark gray (#595959) for titles, gold (#A89968) as primary color, white background.
Dark charcoal (#252829) as secondary color. Sans-serif font (Arial or Helvetica).
Clear axis labels with units. Value labels displayed on each data point.
No gridlines clutter. High resolution, presentation-ready.
A4 landscape aspect ratio (11.69 x 8.27 inches)."""

# Matplotlib style config matching brand colors (gold/gray palette)
MPL_COLORS = [
    "#A89968",  # Gold (theme accent1)
    "#252829",  # Dark charcoal (theme accent2)
    "#595959",  # Dark gray (section headers)
    "#A5A5A5",  # Medium gray (theme accent3)
    "#122A33",  # Dark navy (theme accent6)
    "#9A8A5A",  # Darker gold
    "#F0F0F0",  # Light gray (theme lt2)
    "#000000",  # Pure black
]
MPL_STYLE = {
    "font.family": "sans-serif",
    "axes.facecolor": "#FFFFFF",
    "figure.facecolor": "#FFFFFF",
    "axes.titlesize": 16,
    "axes.titleweight": "bold",
    "axes.titlecolor": "#595959",
    "axes.labelsize": 12,
    "axes.labelcolor": "#595959",
}
plt.rcParams.update(MPL_STYLE)

# Singleton Gemini client — avoids creating a new connection per chart call
_genai_client = None


def _get_genai_client():
    """Return a cached Gemini client (Vertex AI or API key)."""
    global _genai_client
    if _genai_client is None:
        if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE":
            _genai_client = genai.Client(
                vertexai=True,
                project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
                location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
            )
        else:
            _genai_client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    return _genai_client


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
            model=GEMINI_PRO_MODEL,
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
        # Handle both flat 'values' and nested 'series' formats
        if "values" in source_data:
            raw_values = source_data["values"]
        elif "series" in source_data and source_data["series"]:
            raw_values = source_data["series"][0]["values"]
        else:
            raw_values = []
        source_values = {round(float(v), 1) for v in raw_values}
        # Allow 10% tolerance per value
        for sv in source_values:
            found = any(abs(ev - sv) <= abs(sv) * 0.1 + 0.5 for ev in extracted_values)
            if not found:
                return False
        return True
    except Exception as e:
        logger.warning("Chart validation failed: %s", e)
        return False


async def _save_chart_artifact(tool_context: ToolContext, slide_number: int, image_bytes: bytes):
    """Save chart image as ADK artifact and store reference in state."""
    filename = f"slide_{slide_number:02d}_chart.png"
    artifact = genai_types.Part.from_bytes(data=image_bytes, mime_type="image/png")
    await tool_context.save_artifact(filename, artifact)
    tool_context.state[f"slide_{slide_number:02d}_chart_image"] = filename


# --- Matplotlib fallback renderers ---

def _render_matplotlib_bar_chart(data: dict) -> bytes:
    """Render a bar chart with matplotlib, return PNG bytes."""
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(data["categories"], data["values"], color=MPL_COLORS[0])
    ax.set_title(data.get("title", ""), fontsize=16, fontweight="bold", color="#595959")
    ax.set_xlabel(data.get("x_label", ""), fontsize=12)
    ax.set_ylabel(data.get("y_label", ""), fontsize=12)
    for bar, val in zip(bars, data["values"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            bar.get_height(),
            _format_large_number(val),
            ha="center", va="bottom", fontsize=10,
        )
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _render_matplotlib_line_chart(data: dict) -> bytes:
    """Render a line chart with matplotlib, return PNG bytes.

    Dual y-axes when there are two series and y_left_label/y_right_label are provided
    (e.g. revenue on left, users/clients on right).
    """
    series_list = data.get("series", [{"values": data.get("values", [])}])
    categories = data.get("categories", [])

    use_dual_axis = (
        len(series_list) >= 2
        and (data.get("y_left_label") or data.get("y_right_label"))
    )

    if use_dual_axis:
        fig, ax_left = plt.subplots(figsize=(12, 6.2))
        ax_right = ax_left.twinx()

        # Left axis: revenue
        rev_series = series_list[0]
        rev_vals = rev_series["values"]
        color_left = MPL_COLORS[0]
        line_left, = ax_left.plot(
            categories,
            rev_vals,
            marker="o",
            color=color_left,
            label=rev_series.get("label", ""),
            linewidth=2,
        )
        for x, y in zip(categories, rev_vals):
            ax_left.annotate(
                _format_large_number(y),
                (x, y),
                textcoords="offset points",
                xytext=(0, 10),
                ha="center",
                fontsize=9,
                color=color_left,
            )
        y_left_label = data.get("y_left_label") or "Revenue (USD)"
        y_right_label = data.get("y_right_label") or "Number of Users"
        ax_left.set_ylabel(y_left_label, fontsize=12, color=color_left)
        ax_left.tick_params(axis="y", labelcolor=color_left)

        # Right axis: users
        user_series = series_list[1]
        user_vals = user_series["values"]
        color_right = MPL_COLORS[1]
        line_right, = ax_right.plot(
            categories,
            user_vals,
            marker="o",
            color=color_right,
            label=user_series.get("label", ""),
            linewidth=2,
        )
        for x, y in zip(categories, user_vals):
            ax_right.annotate(
                _format_large_number(y),
                (x, y),
                textcoords="offset points",
                xytext=(0, -12),
                ha="center",
                fontsize=9,
                color=color_right,
            )
        ax_right.set_ylabel(y_right_label, fontsize=12, color=color_right)
        ax_right.tick_params(axis="y", labelcolor=color_right)

        ax_left.set_title(
            data.get("title", ""),
            fontsize=16,
            fontweight="bold",
            color="#595959",
        )
        ax_left.set_xlabel(data.get("x_label", ""), fontsize=12)

        # Combined legend
        lines = [line_left, line_right]
        labels = [l.get_label() for l in lines]
        ax_left.legend(lines, labels, loc="upper left")
        ax_left.set_ylim(bottom=0)
        ax_right.set_ylim(bottom=0)
    else:
        fig, ax = plt.subplots(figsize=(12, 6.2))
        for i, series in enumerate(series_list):
            label = series.get("label", "")
            values = series["values"]
            ax.plot(
                categories,
                values,
                marker="o",
                color=MPL_COLORS[i % len(MPL_COLORS)],
                label=label,
                linewidth=2,
            )
            for x, y in zip(categories, values):
                ax.annotate(
                    _format_large_number(y),
                    (x, y),
                    textcoords="offset points",
                    xytext=(0, 10),
                    ha="center",
                    fontsize=9,
                )
        ax.set_title(
            data.get("title", ""),
            fontsize=16,
            fontweight="bold",
            color="#595959",
        )
        ax.set_xlabel(data.get("x_label", ""), fontsize=12)
        ax.set_ylabel(data.get("y_label", ""), fontsize=12)
        if any(s.get("label") for s in series_list):
            ax.legend()
        ax.set_ylim(bottom=0)

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
    ax.set_title(data.get("title", ""), fontsize=16, fontweight="bold", color="#595959")
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# Max milestones per image so each fits one PDF page (content ~6.9in; fig_h = n*0.75)
ROADMAP_MILESTONES_PER_PAGE = 9
# Cell spacing: each box has headline on line 1, description on line 2 below it
ROADMAP_CELL_STEP = 0.095
ROADMAP_BOX_HEIGHT = 0.078


def _render_roadmap_timeline(data: dict) -> bytes:
    """Render one page of a vertical strategic roadmap timeline. Returns PNG bytes."""
    return _render_roadmap_timeline_page(
        data.get("title", "Strategic Growth Roadmap"),
        data.get("milestones", []),
        page_title_suffix="",
    )


def _render_roadmap_timeline_page(title: str, milestones: list, page_title_suffix: str = "") -> bytes:
    """Render a single page of milestones (used for first or continuation page)."""
    if not milestones:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.text(0.5, 0.5, "No milestones extracted", ha="center", va="center", fontsize=14)
        ax.axis("off")
    else:
        n = len(milestones)
        fig_h = max(5, n * 0.75)
        fig, ax = plt.subplots(figsize=(10, fig_h))
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        ax.set_facecolor("#FFFFFF")
        fig.patch.set_facecolor("#FFFFFF")

        line_x = 0.22
        top_y, bottom_y = 0.92, 0.04
        ax.plot([line_x, line_x], [top_y, bottom_y], color="#9a9a9a", linewidth=1.2, zorder=0)

        status_color = {"past": "#252829", "near_future": "#A89968", "long_term": "#122A33"}
        box_h = ROADMAP_BOX_HEIGHT
        step = ROADMAP_CELL_STEP
        for i, m in enumerate(milestones):
            status = m.get("status", "past")
            color = status_color.get(status, "#393E41")
            y = top_y - i * step
            period = m.get("period", "")
            headline = m.get("headline", "")
            desc = m.get("description", "")

            box_x = line_x + 0.04
            box_w = 0.72
            box_top = y + box_h / 2
            box_bottom = y - box_h / 2
            # Draw box first so text sits on top
            ax.add_patch(FancyBboxPatch((box_x, box_bottom), box_w, box_h, boxstyle="round,pad=0.004", facecolor="white", edgecolor=color, linewidth=1.2, zorder=1))
            ax.scatter([line_x], [y], s=50, c=color, zorder=2, edgecolors="white", linewidths=1)
            ax.text(line_x - 0.01, y, period, ha="right", va="center", fontsize=9, color=color)
            # Headline on first line at top of box
            ax.text(box_x + 0.01, box_top - 0.012, headline, ha="left", va="top", fontsize=9, fontweight="bold", color=color, wrap=True)
            # Description on new line below headline, inside same box
            ax.text(box_x + 0.01, box_top - 0.036, desc, ha="left", va="top", fontsize=8, color="#333", wrap=True)

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", pad_inches=0.15, facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _format_large_number(value: float) -> str:
    """Format large numbers with K/M/B suffixes for readable chart labels."""
    abs_val = abs(value)
    if abs_val >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    elif abs_val >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    elif abs_val >= 1_000:
        return f"{value / 1_000:.0f}K"
    else:
        return f"{value:,.0f}"


MPL_RENDERERS = {
    "bar": _render_matplotlib_bar_chart,
    "line": _render_matplotlib_line_chart,
    "pie": _render_matplotlib_pie_chart,
}


# --- Core chart generation logic ---

async def _generate_chart(
    chart_type: str, data_json: str, slide_number: int, tool_context: ToolContext
) -> dict:
    """Shared chart generation logic: Gemini first, matplotlib fallback."""
    try:
        data = json.loads(data_json)
    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"Invalid chart data JSON: {e}"}

    # Step 1: Try Gemini image generation
    try:
        client = _get_genai_client()
        type_desc = {"bar": "bar chart", "line": "line chart", "pie": "pie chart"}.get(chart_type, "chart")

        # Handle both flat 'values' and nested 'series' formats
        if "values" in data:
            values = data["values"]
        elif "series" in data and data["series"]:
            values = data["series"][0]["values"]
        else:
            raise KeyError("values")

        values_desc = "\n".join(
            f"  - {c}: {v}" for c, v in zip(data["categories"], values)
        )
        prompt = f"""{CHART_STYLE_PROMPT}
Create a {type_desc} with title: "{data.get('title', '')}"
X-axis label: "{data.get('x_label', '')}", Y-axis label: "{data.get('y_label', '')}"
Categories and exact values (render these numbers precisely on the chart):
{values_desc}
"""
        response = client.models.generate_content(
            model=GEMINI_IMAGE_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(response_modalities=["Image"]),
        )
        image_bytes = _extract_image_bytes(response)

        if image_bytes and _validate_chart_numbers(client, image_bytes, data):
            await _save_chart_artifact(tool_context, slide_number, image_bytes)
            return {"status": "success", "method": "gemini_image_gen", "chart_type": chart_type}
    except Exception as e:
        logger.warning("Gemini image generation failed for slide %d, falling back to matplotlib: %s", slide_number, e)

    # Step 2: Fallback to matplotlib
    renderer = MPL_RENDERERS.get(chart_type, _render_matplotlib_bar_chart)
    image_bytes = renderer(data)
    await _save_chart_artifact(tool_context, slide_number, image_bytes)
    return {"status": "success", "method": "matplotlib_fallback", "chart_type": chart_type}


# --- ADK Tool Functions ---
# slide_number is NO LONGER an LLM-provided parameter.
# The slide_agent_factory creates bound wrappers with the correct slide_number
# pre-injected, so the LLM only needs to provide data_json.


def make_chart_tool(chart_type: str, slide_number: int):
    """Create a chart generation tool pre-bound to a specific slide number.

    Returns an async function with only `data_json` and `tool_context` as
    parameters — the LLM doesn't need to know which slide number it is.
    """
    type_names = {"bar": "bar_chart", "line": "line_chart", "pie": "pie_chart"}
    type_descs = {"bar": "bar chart", "line": "line chart", "pie": "pie chart"}
    func_name = f"generate_{type_names[chart_type]}"
    type_desc = type_descs[chart_type]

    async def _tool(data_json: str, tool_context: ToolContext) -> dict:
        return await _generate_chart(chart_type, data_json, slide_number, tool_context)

    # Set function metadata for ADK tool discovery
    _tool.__name__ = func_name
    _tool.__qualname__ = func_name
    _tool.__doc__ = f"""Generate a {type_desc} from structured data.

    Args:
        data_json: JSON string with keys: categories (list[str]), series (list with label/values),
                   title (str), x_label (str), y_label (str), value_format (str, optional).
                   For dual y-axis line charts: y_left_label (str, optional), y_right_label (str, optional).

    Returns:
        Status dict with generation method used.
    """
    return _tool


def make_roadmap_tool(slide_number: int):
    """Create a roadmap timeline tool pre-bound to a slide number. Renders vertical timeline image(s); continues on next page when many milestones."""

    async def _tool(data_json: str, tool_context: ToolContext) -> dict:
        try:
            data = json.loads(data_json)
        except json.JSONDecodeError as e:
            return {"status": "error", "message": f"Invalid roadmap JSON: {e}"}
        title = data.get("title", "Strategic Growth Roadmap")
        milestones = data.get("milestones", [])
        if not milestones:
            image_bytes = _render_roadmap_timeline(data)
            await _save_chart_artifact(tool_context, slide_number, image_bytes)
            return {"status": "success", "chart_type": "roadmap", "pages": 1}
        per_page = ROADMAP_MILESTONES_PER_PAGE
        chunks = [milestones[i : i + per_page] for i in range(0, len(milestones), per_page)]
        for p, chunk in enumerate(chunks):
            page_suffix = f"(cont. p{p + 1})" if len(chunks) > 1 and p > 0 else ""
            image_bytes = _render_roadmap_timeline_page(title, chunk, page_suffix)
            if p == 0:
                await _save_chart_artifact(tool_context, slide_number, image_bytes)
            else:
                filename = f"slide_{slide_number:02d}_chart_{p + 1}.png"
                key = f"slide_{slide_number:02d}_chart_image_{p + 1}"
                artifact = genai_types.Part.from_bytes(data=image_bytes, mime_type="image/png")
                await tool_context.save_artifact(filename, artifact)
                tool_context.state[key] = filename
        return {"status": "success", "chart_type": "roadmap", "pages": len(chunks)}

    _tool.__name__ = "generate_roadmap_timeline"
    _tool.__qualname__ = "generate_roadmap_timeline"
    _tool.__doc__ = """Generate a strategic roadmap timeline from structured data. Pass the full milestones list; if it exceeds one page, multiple images are generated (each fits one PDF page).

    Args:
        data_json: JSON string with keys: title (str), milestones (list of objects).
                   Each milestone: period (str), headline (str), description (str),
                   status (str: "past" | "near_future" | "long_term").

    Returns:
        Status dict.
    """
    return _tool

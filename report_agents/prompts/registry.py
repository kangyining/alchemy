"""Central registry mapping slide specs to prompts, types, and chart configurations.

This is the single source of truth for what slides exist and how they behave.
Adding/removing slides = editing SLIDE_REGISTRY.
"""

from dataclasses import dataclass
from enum import Enum


class SlideType(Enum):
    """Output format of the slide - determines which tools are attached."""
    TEXT = "text"
    TABLE = "table"
    CHART = "chart"
    MIXED = "mixed"  # text + chart on same slide
    ROADMAP = "roadmap"  # vertical timeline image from structured milestone data


class ChartType(Enum):
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    NONE = "none"


class ContextType(Enum):
    """Input context size - determines how much document context is injected."""
    SUMMARY = "summary"  # First few sections, no tables (for high-level slides)
    FULL = "full"        # Complete document context with all tables


@dataclass
class SlideSpec:
    slide_number: int
    title: str
    slide_type: SlideType
    chart_type: ChartType
    context_type: ContextType
    prompt: str


# Accuracy instructions appended to every slide agent prompt
ACCURACY_SUFFIX = """
CRITICAL RULES — you MUST follow these:
1. Every number you include MUST appear verbatim in the source documents.
2. If a number is not found in the source, write [NOT FOUND IN SOURCE] instead of guessing.
3. End your output with a "Sources" section citing the filename for each figure. Do NOT use bold (**) in the Sources section — keep it plain text.
4. For any calculations (YoY growth, margins, ratios), use the calculate_financial_metrics tool — do NOT compute numbers yourself.
5. Output your response as markdown. Highlight key points with **bold** so they stand out in the PDF.
6. DATA SOURCE PRIORITY: If `query_financial_data` is available, you MUST call it first to get numerical data from SQLite. If the query returns rows, use that data — do NOT pull the same numbers from the document text. Only fall back to document text when the SQL query returns no rows or no relevant columns for what you need.
"""

COVER_PAGE_SUFFIX = """
Output your response as markdown. Do NOT use bold (**) markers.
"""

# Import prompts from individual files
from report_agents.prompts.slide_01_cover import PROMPT as SLIDE_01_PROMPT
from report_agents.prompts.slide_02_executive_summary import PROMPT as SLIDE_02_PROMPT
from report_agents.prompts.slide_03_revenue_breakdown import PROMPT as SLIDE_03_PROMPT
from report_agents.prompts.slide_04_roadmap_analysis import PROMPT as SLIDE_04_PROMPT
from report_agents.prompts.slide_05_roadmap_extraction import PROMPT as SLIDE_05_PROMPT
from report_agents.prompts.slide_06_risks_mitigations import PROMPT as SLIDE_06_PROMPT
from report_agents.prompts.slide_07_recommendations_approvals import PROMPT as SLIDE_07_PROMPT


SLIDE_REGISTRY: list[SlideSpec] = [
    SlideSpec(
        slide_number=1,
        title="Cover Page",
        slide_type=SlideType.TEXT,
        chart_type=ChartType.NONE,
        context_type=ContextType.SUMMARY,
        prompt=SLIDE_01_PROMPT + COVER_PAGE_SUFFIX,
    ),
    SlideSpec(
        slide_number=2,
        title="Executive Summary",
        slide_type=SlideType.TEXT,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SLIDE_02_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=3,
        title="Revenue Breakdown",
        slide_type=SlideType.CHART,
        chart_type=ChartType.LINE,
        context_type=ContextType.FULL,
        prompt=SLIDE_03_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=4,
        title="Market Analysis",
        slide_type=SlideType.TABLE,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SLIDE_04_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=5,
        title="Company Roadmap",
        slide_type=SlideType.ROADMAP,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SLIDE_05_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=6,
        title="Key Risks & Mitigants",
        slide_type=SlideType.TABLE,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SLIDE_06_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=7,
        title="Recommendations & Approvals",
        slide_type=SlideType.TABLE,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SLIDE_07_PROMPT + ACCURACY_SUFFIX,
    ),
]

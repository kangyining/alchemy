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
3. End your output with a "Sources" section citing the filename for each figure.
4. For any calculations (YoY growth, margins, ratios), use the calculate_financial_metrics tool — do NOT compute numbers yourself.
5. Output your response as markdown.
"""

# Import prompts from individual files
from report_agents.prompts.slide_01_cover import PROMPT as SLIDE_01_PROMPT
from report_agents.prompts.slide_02_executive_summary import PROMPT as SLIDE_02_PROMPT
from report_agents.prompts.slide_03_financial_highlights import PROMPT as SLIDE_03_PROMPT
from report_agents.prompts.slide_04_revenue_breakdown import PROMPT as SLIDE_04_PROMPT
from report_agents.prompts.slide_05_expense_analysis import PROMPT as SLIDE_05_PROMPT
from report_agents.prompts.slide_06_profitability import PROMPT as SLIDE_06_PROMPT
from report_agents.prompts.slide_07_balance_sheet import PROMPT as SLIDE_07_PROMPT
from report_agents.prompts.slide_08_cash_flow import PROMPT as SLIDE_08_PROMPT
from report_agents.prompts.slide_09_key_ratios import PROMPT as SLIDE_09_PROMPT
from report_agents.prompts.slide_10_outlook import PROMPT as SLIDE_10_PROMPT
from report_agents.prompts.slide_11_risks_recommendations import PROMPT as SLIDE_11_PROMPT
from report_agents.prompts.slide_12_roadmap_analysis import PROMPT as SLIDE_12_PROMPT
from report_agents.prompts.slide_13_roadmap_extraction import PROMPT as SLIDE_13_PROMPT
from report_agents.prompts.slide_14_recommendations_approvals import PROMPT as SLIDE_14_PROMPT


SLIDE_REGISTRY: list[SlideSpec] = [
    SlideSpec(
        slide_number=1,
        title="Cover Page",
        slide_type=SlideType.TEXT,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SLIDE_01_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=2,
        title="Executive Summary",
        slide_type=SlideType.TEXT,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,  # Needs revenue/income figures from tables
        prompt=SLIDE_02_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=3,
        title="Financial Highlights",
        slide_type=SlideType.TABLE,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SLIDE_03_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=4,
        title="Revenue Breakdown",
        slide_type=SlideType.CHART,
        chart_type=ChartType.LINE,
        context_type=ContextType.FULL,
        prompt=SLIDE_04_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=5,
        title="Expense Analysis",
        slide_type=SlideType.CHART,
        chart_type=ChartType.PIE,
        context_type=ContextType.FULL,
        prompt=SLIDE_05_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=6,
        title="Profitability Trends",
        slide_type=SlideType.CHART,
        chart_type=ChartType.LINE,
        context_type=ContextType.FULL,
        prompt=SLIDE_06_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=7,
        title="Balance Sheet Summary",
        slide_type=SlideType.TABLE,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SLIDE_07_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=8,
        title="Cash Flow Analysis",
        slide_type=SlideType.MIXED,
        chart_type=ChartType.BAR,
        context_type=ContextType.FULL,
        prompt=SLIDE_08_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=9,
        title="Key Financial Ratios",
        slide_type=SlideType.TABLE,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SLIDE_09_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=10,
        title="Outlook & Recommendations",
        slide_type=SlideType.TEXT,
        chart_type=ChartType.NONE,
        context_type=ContextType.SUMMARY,
        prompt=SLIDE_10_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=11,
        title="Key Risks & Mitigants",
        slide_type=SlideType.TABLE,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SLIDE_11_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=12,
        title="Roadmap Market Analysis",
        slide_type=SlideType.TABLE,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SLIDE_12_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=13,
        title="Company Roadmap",
        slide_type=SlideType.ROADMAP,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SLIDE_13_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=14,
        title="Recommendations & Approvals",
        slide_type=SlideType.TABLE,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SLIDE_14_PROMPT + ACCURACY_SUFFIX,
    ),
]

"""Factory that creates one LlmAgent per slide from the prompt registry."""

from google.adk.agents import LlmAgent

from report_agents.prompts.registry import SLIDE_REGISTRY, SlideType, ChartType
from report_agents.tools.chart_generator import (
    generate_bar_chart,
    generate_line_chart,
    generate_pie_chart,
)
from report_agents.tools.financial_calc import calculate_financial_metrics
from report_agents.utils.state_keys import slide_content_key

# Map chart types to tool functions
CHART_TOOLS = {
    ChartType.BAR: generate_bar_chart,
    ChartType.LINE: generate_line_chart,
    ChartType.PIE: generate_pie_chart,
}

MODEL = "gemini-2.5-pro"


def create_slide_agents() -> list[LlmAgent]:
    """Create one LlmAgent per slide from the registry.

    Text slides get only the financial calc tool.
    Chart/mixed slides additionally get the appropriate chart tool.
    Each agent writes to a unique output_key in session state.
    """
    agents = []
    for spec in SLIDE_REGISTRY:
        tools = [calculate_financial_metrics]

        if spec.slide_type in (SlideType.CHART, SlideType.MIXED):
            chart_tool = CHART_TOOLS.get(spec.chart_type)
            if chart_tool:
                tools.append(chart_tool)

        import re
        safe_title = re.sub(r"[^a-zA-Z0-9_]", "", spec.title.replace(" ", "_"))
        agent = LlmAgent(
            name=f"SlideAgent_{spec.slide_number:02d}_{safe_title}",
            model=MODEL,
            instruction=spec.prompt,
            tools=tools,
            output_key=slide_content_key(spec.slide_number),
        )
        agents.append(agent)

    return agents

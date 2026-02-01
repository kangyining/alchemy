"""Factory that creates one LlmAgent per slide from the prompt registry."""

import re

from google.adk.agents import LlmAgent

from report_agents.prompts.registry import SLIDE_REGISTRY, SlideType, ChartType
from report_agents.tools.chart_generator import make_chart_tool
from report_agents.tools.financial_calc import calculate_financial_metrics
from report_agents.utils.callbacks import prepare_slide_request
from report_agents.utils.state_keys import slide_content_key

# Map ChartType enum to the chart_type string expected by make_chart_tool
CHART_TYPE_MAP = {
    ChartType.BAR: "bar",
    ChartType.LINE: "line",
    ChartType.PIE: "pie",
}

MODEL = "gemini-3-pro-preview"


def create_slide_agents() -> list[LlmAgent]:
    """Create one LlmAgent per slide from the registry.

    Text slides get only the financial calc tool.
    Chart/mixed slides additionally get a chart tool pre-bound to their
    slide number — the LLM never needs to provide the slide number.
    Each agent writes to a unique output_key in session state.
    """
    agents = []
    for spec in SLIDE_REGISTRY:
        tools = [calculate_financial_metrics]

        if spec.slide_type in (SlideType.CHART, SlideType.MIXED):
            chart_type_str = CHART_TYPE_MAP.get(spec.chart_type)
            if chart_type_str:
                tools.append(make_chart_tool(chart_type_str, spec.slide_number))

        safe_title = re.sub(r"[^a-zA-Z0-9_]", "", spec.title.replace(" ", "_"))
        agent = LlmAgent(
            name=f"SlideAgent_{spec.slide_number:02d}_{safe_title}",
            model=MODEL,
            instruction=spec.prompt,
            tools=tools,
            output_key=slide_content_key(spec.slide_number),
            before_model_callback=prepare_slide_request,
        )
        agents.append(agent)

    return agents

"""Factory that creates one LlmAgent per slide from the prompt registry."""

import asyncio
import re
from collections.abc import AsyncGenerator

from google.adk.agents import LlmAgent
from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.models.google_llm import Gemini
from google.genai import types as genai_types

from report_agents.prompts.registry import SLIDE_REGISTRY, SlideType, ChartType, ContextType
from report_agents.tools.chart_generator import make_chart_tool
from report_agents.tools.data_query import query_financial_data, list_available_tables
from report_agents.tools.financial_calc import calculate_financial_metrics
from report_agents.utils.callbacks import (
    prepare_full_context_request,
    prepare_summary_context_request,
    log_token_usage,
    handle_model_error,
)
from report_agents.utils.state_keys import slide_content_key

# Map ChartType enum to the chart_type string expected by make_chart_tool
CHART_TYPE_MAP = {
    ChartType.BAR: "bar",
    ChartType.LINE: "line",
    ChartType.PIE: "pie",
}

MODEL = Gemini(
    model="gemini-3-flash-preview",
    retry_options=genai_types.HttpRetryOptions(
        initial_delay=60, max_delay=60, attempts=3,
    ),
)

# Seconds to pause between slide agents to spread token usage across TPM windows
INTER_SLIDE_DELAY_SECONDS = 10


class ThrottleAgent(BaseAgent):
    """Deterministic agent that sleeps to spread TPM usage across minute windows."""

    delay_seconds: float = INTER_SLIDE_DELAY_SECONDS

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        await asyncio.sleep(self.delay_seconds)
        yield Event(
            author=self.name,
            content=genai_types.Content(
                role="model",
                parts=[genai_types.Part.from_text(
                    text=f"Throttle: waited {self.delay_seconds}s before next slide."
                )],
            ),
        )


def create_slide_agents() -> list[BaseAgent]:
    """Create one LlmAgent per slide from the registry.

    Document content is injected via the before_model_callback (context stuffing).
    TEXT slides get a shorter summary context; TABLE/CHART/MIXED slides get full context.
    Slides get the financial calc tool, and chart/mixed slides additionally get
    a chart tool pre-bound to their slide number.
    Each agent writes to a unique output_key in session state.
    """
    agents: list[BaseAgent] = []
    for spec in SLIDE_REGISTRY:
        if spec.slide_number not in (1, 2):  # TODO: remove filter after testing
            continue

        # Insert throttle between slides (not before the first one)
        if agents:
            agents.append(ThrottleAgent(
                name=f"Throttle_before_{spec.slide_number:02d}",
                delay_seconds=INTER_SLIDE_DELAY_SECONDS,
            ))

        tools = [calculate_financial_metrics]

        # Add query tools for FULL context slides (TABLE/CHART/MIXED)
        if spec.context_type == ContextType.FULL:
            tools.extend([query_financial_data, list_available_tables])

        if spec.slide_type in (SlideType.CHART, SlideType.MIXED):
            chart_type_str = CHART_TYPE_MAP.get(spec.chart_type)
            if chart_type_str:
                tools.append(make_chart_tool(chart_type_str, spec.slide_number))

        # Select context callback based on context_type (not slide_type)
        if spec.context_type == ContextType.SUMMARY:
            before_callback = prepare_summary_context_request
        else:
            before_callback = prepare_full_context_request

        safe_title = re.sub(r"[^a-zA-Z0-9_]", "", spec.title.replace(" ", "_"))
        agent = LlmAgent(
            name=f"SlideAgent_{spec.slide_number:02d}_{safe_title}",
            model=MODEL,
            instruction=spec.prompt,
            tools=tools,
            output_key=slide_content_key(spec.slide_number),
            before_model_callback=before_callback,
            after_model_callback=log_token_usage,
            on_model_error_callback=handle_model_error,
        )
        agents.append(agent)

    return agents

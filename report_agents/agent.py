"""Root orchestrator agent for financial report generation.

This is the entry point that ADK discovers via `adk web`.
It wires together the three-phase pipeline:
  1. Ingestion — parse uploaded documents with Document AI (deterministic)
  2. Parallel slide generation — slide agents run concurrently for speed
  3. Assembly — build PPTX + PDF from all slide outputs (deterministic)
"""

from google.adk.agents import SequentialAgent, ParallelAgent
from google.adk.apps.app import App
from google.adk.agents.context_cache_config import ContextCacheConfig

from report_agents.sub_agents.ingestion_agent import ingestion_agent
from report_agents.sub_agents.slide_agent_factory import create_slide_agents
from report_agents.sub_agents.assembly_agent import assembly_agent

# Create all slide agents from the registry
slide_agents = create_slide_agents()

# Use ParallelAgent to run all slide agents concurrently.
# This significantly reduces latency compared to SequentialAgent.
# Each agent receives relevant document context via its before_model_callback.
parallel_slide_generation = ParallelAgent(
    name="ParallelSlideGeneration",
    sub_agents=slide_agents,
)

# Root orchestrator — Phase 1 must complete before Phase 2, and Phase 2 before Phase 3.
root_agent = SequentialAgent(
    name="FinancialReportOrchestrator",
    sub_agents=[
        ingestion_agent,                # Phase 1: Parse documents (deterministic)
        parallel_slide_generation,       # Phase 2: Generate slides in parallel
        assembly_agent,                 # Phase 3: Build PPTX + PDF (deterministic)
    ],
)

# Export App with context caching — adk web discovers this automatically.
app = App(
    name="report_agents",
    root_agent=root_agent,
    context_cache_config=ContextCacheConfig(
        min_tokens=2048,
        ttl_seconds=1800,
        cache_intervals=1,
    ),
)

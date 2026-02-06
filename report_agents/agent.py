"""Root orchestrator agent for financial report generation.

This is the entry point that ADK discovers via `adk web`.
It wires together the three-phase pipeline:
  1. Ingestion — parse uploaded documents with Document AI (deterministic)
  2. Sequential slide generation — slide agents run one at a time to avoid rate limits
  3. Assembly — build PPTX + PDF from all slide outputs (deterministic)
"""

from google.adk.agents import SequentialAgent
from google.adk.apps.app import App
from google.adk.agents.context_cache_config import ContextCacheConfig

from report_agents.sub_agents.ingestion_agent import ingestion_agent
from report_agents.sub_agents.slide_agent_factory import create_slide_agents
from report_agents.sub_agents.assembly_agent import assembly_agent

# Create all slide agents from the registry
slide_agents = create_slide_agents()

# Use SequentialAgent to run slide agents one at a time.
# This prevents TPM (Tokens Per Minute) explosion with Gemini 3 preview models.
# Each agent receives relevant document context via its before_model_callback.
sequential_slide_generation = SequentialAgent(
    name="SequentialSlideGeneration",
    sub_agents=slide_agents,
)

# Root orchestrator — Phase 1 must complete before Phase 2, and Phase 2 before Phase 3.
root_agent = SequentialAgent(
    name="FinancialReportOrchestrator",
    sub_agents=[
        ingestion_agent,                # Phase 1: Parse documents (deterministic)
        sequential_slide_generation,    # Phase 2: Generate slides sequentially
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

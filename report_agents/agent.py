"""Root orchestrator agent for financial report generation.

This is the entry point that ADK discovers via `adk web`.
It wires together the three-phase pipeline:
  1. Ingestion — parse uploaded documents with Document AI (deterministic)
  2. Parallel slide generation — all slide agents run concurrently
  3. Assembly — build PPTX + PDF from all slide outputs (deterministic)
"""

from google.adk.agents import ParallelAgent, SequentialAgent
from google.adk.apps.app import App
from google.adk.agents.context_cache_config import ContextCacheConfig

from report_agents.sub_agents.ingestion_agent import ingestion_agent
from report_agents.sub_agents.summary_agent import summary_agent
from report_agents.sub_agents.slide_agent_factory import create_slide_agents
from report_agents.sub_agents.assembly_agent import assembly_agent

# Create all slide agents from the registry
slide_agents = create_slide_agents()

# Wrap slide agents in ParallelAgent for concurrent execution
parallel_slide_generation = ParallelAgent(
    name="ParallelSlideGeneration",
    sub_agents=slide_agents,
)

# Root orchestrator — no before_agent_callback needed since the
# IngestionAgent (BaseAgent) sets state deterministically.
root_agent = SequentialAgent(
    name="FinancialReportOrchestrator",
    sub_agents=[
        ingestion_agent,             # Phase 1: Parse documents (deterministic)
        summary_agent,               # Phase 1.5: Summarize documents
        parallel_slide_generation,   # Phase 2: Generate all slides in parallel
        assembly_agent,              # Phase 3: Build PPTX + PDF (deterministic)
    ],
)

# Export App with context caching — adk web discovers this automatically.
# Caches the large parsed_documents content so all 10 parallel slide agents
# share one cached copy instead of paying for input tokens 10x.
app = App(
    name="report_agents",
    root_agent=root_agent,
    context_cache_config=ContextCacheConfig(
        min_tokens=2048,
        ttl_seconds=1800,
        cache_intervals=10,
    ),
)

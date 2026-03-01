"""Root orchestrator agent for financial report generation.

This is the entry point that ADK discovers via `adk web`.
It wires together the three-phase pipeline:
  1. Ingestion — parse uploaded documents with Document AI (deterministic)
  2. Sequential slide generation — slide agents run one at a time to avoid rate limits
  3. Assembly — build PPTX + PDF from all slide outputs (deterministic)

For testing, set USE_CACHED_INGESTION=true to skip Document AI calls and use
cached parsing results. Generate the cache first with:
    python -m report_agents.scripts.generate_cache
"""

import logging
import os

from google.adk.agents import SequentialAgent
from google.adk.apps.app import App
from google.adk.agents.context_cache_config import ContextCacheConfig

from report_agents.sub_agents.cached_ingestion_agent import cached_ingestion_agent
from report_agents.sub_agents.ingestion_agent import ingestion_agent
from report_agents.sub_agents.slide_agent_factory import create_slide_agents
from report_agents.sub_agents.assembly_agent import assembly_agent

logger = logging.getLogger(__name__)

USE_CACHED_INGESTION = os.environ.get("USE_CACHED_INGESTION", "").lower() in ("true", "1", "yes")

active_ingestion_agent = cached_ingestion_agent if USE_CACHED_INGESTION else ingestion_agent
if USE_CACHED_INGESTION:
    logger.info("Using CACHED ingestion (testing mode)")
else:
    logger.info("Using Document AI ingestion (production mode)")

# Create all slide agents from the registry
slide_agents = create_slide_agents()

# Wrap slide agents in SequentialAgent to avoid rate limits.
# Each agent receives full document context via the before_model_callback.
sequential_slide_generation = SequentialAgent(
    name="SequentialSlideGeneration",
    sub_agents=slide_agents,
)

# Root orchestrator — no before_agent_callback needed since the
# IngestionAgent (BaseAgent) sets state deterministically.
root_agent = SequentialAgent(
    name="FinancialReportOrchestrator",
    sub_agents=[
        active_ingestion_agent,         # Phase 1: Parse documents (or load from cache)
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

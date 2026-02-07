"""Cached ingestion agent for testing — no Document AI calls.

Loads pre-parsed document results from a cache file to avoid
expensive Document AI API calls during development and testing.

Usage:
    1. First, generate cache: python -m report_agents.scripts.generate_cache
    2. Set environment variable: USE_CACHED_INGESTION=true
    3. Run ADK as usual: adk web
"""

import logging
import os
import pickle
from collections.abc import AsyncGenerator
from pathlib import Path

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types as genai_types

from report_agents.services.database_service import FinancialDataStore

logger = logging.getLogger(__name__)

# Default cache location
CACHE_DIR = Path(__file__).parent.parent.parent / ".cache"
CACHE_FILE = CACHE_DIR / "ingestion_cache.pkl"


class CachedIngestionAgent(BaseAgent):
    """Loads pre-parsed document results from cache instead of calling Document AI."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        cache_path = CACHE_FILE
        if not cache_path.exists():
            error_msg = (
                f"Cache file not found: {cache_path}\n"
                "Please generate cache first: python -m report_agents.scripts.generate_cache"
            )
            logger.error(error_msg)
            yield Event(
                author=self.name,
                content=genai_types.Content(
                    role="model",
                    parts=[genai_types.Part.from_text(text=f"Error: {error_msg}")],
                ),
            )
            return

        logger.info("Loading cached ingestion results from: %s", cache_path)

        # Load cached data
        with open(cache_path, "rb") as f:
            cache_data = pickle.load(f)

        # Extract cached values
        state_delta_base = cache_data.get("state_delta", {})
        dataframes = cache_data.get("dataframes", {})

        # Recreate SQLite database for this session
        session_id = ctx.session.id
        table_schemas = ""

        if dataframes:
            store = FinancialDataStore(session_id)
            for key, df in dataframes.items():
                # key format: "source_file:sheet_name"
                parts = key.split(":", 1)
                source_file = parts[0]
                sheet_name = parts[1] if len(parts) > 1 else "Sheet1"
                store.store_dataframe(df, source_file, sheet_name)

            table_schemas = store.get_schema_context()
            logger.info(
                "Restored %d DataFrames from cache to SQLite, schema context: %d chars",
                len(dataframes),
                len(table_schemas),
            )

        # Build state delta with session-specific db_path
        state_delta = {
            "table_schemas": table_schemas,
            "db_path": f"/tmp/report_agents/{session_id}.db",
            "full_text_document_context": state_delta_base.get("full_text_document_context", ""),
            "summary_document_context": state_delta_base.get("summary_document_context", ""),
            "full_document_context": state_delta_base.get("full_document_context", ""),
            "parsed_tables_json": state_delta_base.get("parsed_tables_json", "[]"),
        }

        actions = EventActions(state_delta=state_delta)
        yield Event(
            author=self.name,
            content=genai_types.Content(
                role="model",
                parts=[genai_types.Part.from_text(
                    text=f"Ingestion loaded from cache. "
                    f"Restored {len(dataframes)} tables to SQLite."
                )],
            ),
            actions=actions,
        )


def should_use_cached_ingestion() -> bool:
    """Check if cached ingestion should be used based on environment."""
    return os.environ.get("USE_CACHED_INGESTION", "").lower() in ("true", "1", "yes")


cached_ingestion_agent = CachedIngestionAgent(name="CachedIngestionAgent")

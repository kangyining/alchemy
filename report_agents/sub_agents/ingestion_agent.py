"""Deterministic ingestion agent — no LLM call.

Extends BaseAgent to run Document AI parsing directly, then writes
the results to session state via event state_delta.
"""

import hashlib
import logging
from collections.abc import AsyncGenerator

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types as genai_types

from report_agents.tools.document_parser import (
    _collect_inline_files,
    _get_mime_type,
    parse_documents,
)

logger = logging.getLogger(__name__)


class IngestionAgent(BaseAgent):
    """Deterministic agent that parses uploaded documents without an LLM."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        # 1. Collect files from artifacts first, then inline data fallback
        files: list[tuple[str, bytes, str]] = []

        if ctx.artifact_service:
            artifact_names = await ctx.artifact_service.list_artifact_keys(
                app_name=ctx.app_name,
                user_id=ctx.user_id,
                session_id=ctx.session.id,
            )
            for name in artifact_names:
                try:
                    artifact = await ctx.artifact_service.load_artifact(
                        app_name=ctx.app_name,
                        user_id=ctx.user_id,
                        session_id=ctx.session.id,
                        filename=name,
                    )
                    if artifact and artifact.inline_data:
                        files.append(
                            (name, artifact.inline_data.data, _get_mime_type(name))
                        )
                except Exception as e:
                    logger.warning("Failed to load artifact '%s': %s", name, e)

        # Fallback: collect inline files from user_content
        if not files:
            files = _collect_inline_files(ctx.user_content)

        # Also scan session history for any file parts we may have missed
        if not files:
            for event in ctx.session.events:
                if event.content and event.content.parts:
                    files.extend(_collect_inline_files(event.content))
            # Deduplicate by content hash (same data may appear in multiple events)
            seen: set[str] = set()
            unique_files = []
            for name, data, mime in files:
                content_hash = hashlib.sha256(data).hexdigest()
                if content_hash not in seen:
                    seen.add(content_hash)
                    unique_files.append((name, data, mime))
            files = unique_files

        logger.info("IngestionAgent collected %d file(s): %s",
                     len(files), [f[0] for f in files])

        # 2. Run deterministic Document AI parsing
        result = await parse_documents(files)

        # 3. Emit state delta so downstream agents can read parsed data
        state_delta = {
            "full_document_context": result.get("full_document_context", ""),
            "summary_document_context": result.get("summary_document_context", ""),
            "parsed_tables_json": result.get("parsed_tables_json", "[]"),
        }

        actions = EventActions(state_delta=state_delta)
        yield Event(
            author=self.name,
            content=genai_types.Content(
                role="model",
                parts=[genai_types.Part.from_text(
                    text=f"Ingestion complete: {result.get('status', 'unknown')}"
                )],
            ),
            actions=actions,
        )


ingestion_agent = IngestionAgent(name="IngestionAgent")

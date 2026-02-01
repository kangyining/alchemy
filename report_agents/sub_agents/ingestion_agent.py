"""Deterministic ingestion agent — no LLM call.

Extends BaseAgent to run Document AI parsing directly, then writes
the results to session state via event state_delta.
"""

import json
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
                except Exception:
                    pass

        if not files:
            files = _collect_inline_files(ctx.user_content)

        # 2. Run deterministic Document AI parsing
        result = await parse_documents(files)

        # 3. Emit state delta so downstream agents can read parsed data
        state_delta = {
            "parsed_documents": result.get("parsed_documents", ""),
            "parsed_tables_json": result.get("parsed_tables_json", "[]"),
            "document_sources": result.get("document_sources", []),
            "ingestion_summary": json.dumps({
                k: v for k, v in result.items()
                if k not in ("parsed_documents", "parsed_tables_json")
            }, default=str),
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

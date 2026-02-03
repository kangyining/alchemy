"""Deterministic assembly agent — no LLM call.

Extends BaseAgent to run report assembly directly, saves PPTX and PDF
as artifacts, and emits the result via event state_delta.
"""

import json
import logging
from collections.abc import AsyncGenerator

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types as genai_types

from report_agents.services.database_service import FinancialDataStore
from report_agents.tools.report_builder import assemble_report

logger = logging.getLogger(__name__)


class AssemblyAgent(BaseAgent):
    """Deterministic agent that assembles PPTX + PDF without an LLM."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state

        # Build an artifact loader from the invocation context
        async def load_artifact_fn(filename: str) -> bytes | None:
            if not ctx.artifact_service:
                return None
            try:
                artifact = await ctx.artifact_service.load_artifact(
                    app_name=ctx.app_name,
                    user_id=ctx.user_id,
                    session_id=ctx.session.id,
                    filename=filename,
                )
                if artifact and artifact.inline_data:
                    return artifact.inline_data.data
            except Exception:
                pass
            return None

        # Run deterministic assembly
        result = await assemble_report(state, load_artifact_fn)

        # Save artifacts
        artifact_delta = {}
        if ctx.artifact_service and result.get("pptx_bytes"):
            version = await ctx.artifact_service.save_artifact(
                app_name=ctx.app_name,
                user_id=ctx.user_id,
                session_id=ctx.session.id,
                filename="financial_report.pptx",
                artifact=genai_types.Part.from_bytes(
                    data=result["pptx_bytes"],
                    mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                ),
            )
            artifact_delta["financial_report.pptx"] = version

        if ctx.artifact_service and result.get("pdf_bytes"):
            version = await ctx.artifact_service.save_artifact(
                app_name=ctx.app_name,
                user_id=ctx.user_id,
                session_id=ctx.session.id,
                filename="financial_report.pdf",
                artifact=genai_types.Part.from_bytes(
                    data=result["pdf_bytes"],
                    mime_type="application/pdf",
                ),
            )
            artifact_delta["financial_report.pdf"] = version

        # Cleanup session-scoped SQLite database after assembly completes
        db_cleanup_status = "skipped"
        try:
            FinancialDataStore(ctx.session.id).cleanup()
            db_cleanup_status = "deleted"
        except Exception as e:
            logger.warning("DB cleanup failed for session %s: %s", ctx.session.id, e)
            db_cleanup_status = "error"

        summary = {
            "status": result.get("status", "unknown"),
            "slides_generated": result.get("slides_generated", 0),
            "artifacts": list(artifact_delta.keys()),
            "db_cleanup": db_cleanup_status,
        }

        actions = EventActions(
            state_delta={"assembly_result": json.dumps(summary)},
            artifact_delta=artifact_delta,
        )
        yield Event(
            author=self.name,
            content=genai_types.Content(
                role="model",
                parts=[genai_types.Part.from_text(
                    text=f"Assembly complete: {summary['slides_generated']} slides, "
                         f"artifacts: {', '.join(summary['artifacts']) or 'none'}"
                )],
            ),
            actions=actions,
        )


assembly_agent = AssemblyAgent(name="ReportAssemblyAgent")

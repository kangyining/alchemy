"""Status agent — runs first in the pipeline.

Generates a unique run_id (timestamp), writes an in_progress status record
to GCS, and stores run_id + started_at in session state for downstream agents.
"""

import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types as genai_types

from report_agents.services.run_status import write_status

logger = logging.getLogger(__name__)


class StatusAgent(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        now = datetime.now(timezone.utc)
        run_id = now.strftime("%Y%m%d_%H%M%S")
        started_at = now.isoformat()
        user_id = ctx.user_id or "anonymous"

        write_status(user_id, run_id, {
            "run_id": run_id,
            "status": "in_progress",
            "started_at": started_at,
            "message": "Parsing documents...",
        })
        logger.info("Run %s started for user %s", run_id, user_id)

        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={"run_id": run_id, "run_started_at": started_at},
            ),
            content=genai_types.Content(
                role="model",
                parts=[genai_types.Part.from_text(text=f"Starting run {run_id}.")],
            ),
        )


status_agent = StatusAgent(name="StatusAgent")

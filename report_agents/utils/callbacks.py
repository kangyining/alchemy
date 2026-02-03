"""Callbacks for ADK agent hooks."""

import logging
import time

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.genai import types as genai_types

logger = logging.getLogger(__name__)

# Backoff constants for on_model_error_callback (flat 60s for TPM window)
BACKOFF_STATE_KEY = "_llm_backoff"
BACKOFF_BASE_SECONDS = 60.0
BACKOFF_MAX_SECONDS = 60.0
BACKOFF_MULTIPLIER = 1.0


def strip_file_parts(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> None:
    """Remove all inline file/data parts from the LLM request.

    Uploaded documents are stored as ADK artifacts and accessed by tools
    (Document AI, etc.) directly.  Stripping them from the model request
    avoids duplicate processing, wasted tokens, and Gemini 400 errors for
    unsupported formats like DOCX/XLSX.

    If stripping leaves a content with no parts (e.g. the user only uploaded
    files with no accompanying text), a placeholder text part is inserted so
    the request remains valid for Gemini.
    """
    for content in llm_request.contents:
        if not content.parts:
            continue
        content.parts = [
            part for part in content.parts if not part.inline_data
        ]
        if not content.parts:
            content.parts = [
                genai_types.Part.from_text(
                    text="Documents have been uploaded for processing."
                )
            ]


def _inject_context(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
    state_key: str,
) -> None:
    """Strip file parts and inject document context from the given state key."""
    strip_file_parts(callback_context, llm_request)
    context_text = callback_context.state.get(state_key, "")
    if context_text:
        context_content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text=context_text)],
        )
        llm_request.contents.insert(0, context_content)


def prepare_full_context_request(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> None:
    """before_model_callback for TABLE/CHART/MIXED slides.

    Injects full text context for non-spreadsheet sources, plus table schema
    metadata for spreadsheet data so the agent can query as needed.

    This avoids injecting full spreadsheet tables while preserving narrative
    text from PDFs/docs.
    """
    strip_file_parts(callback_context, llm_request)

    # Inject non-spreadsheet text context (full, untruncated)
    text_context = callback_context.state.get("full_text_document_context", "")

    # Inject schema metadata for spreadsheet data
    table_schemas = callback_context.state.get("table_schemas", "")
    context_blocks: list[str] = []
    if text_context:
        context_blocks.append(text_context)
    if table_schemas:
        context_blocks.append(
            f"{table_schemas}\n\n"
            "Use the `query_financial_data` tool to fetch specific data you need. "
            "Example queries:\n"
            "- 'Get revenue and net income figures'\n"
            "- 'Show all data from the Income Statement sheet'\n"
            "- 'Find gross profit margin and operating expenses'"
        )

    if context_blocks:
        context_content = genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text="\n\n".join(context_blocks))],
        )
        llm_request.contents.insert(0, context_content)


def prepare_summary_context_request(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> None:
    """before_model_callback for TEXT-only slides (Cover, Exec Summary, Outlook).

    Injects a shorter summary context (first few sections per source, no tables)
    to reduce token usage on slides that only need high-level information.
    """
    _inject_context(callback_context, llm_request, "summary_document_context")


def log_token_usage(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> None:
    """Log token usage after each LLM call.

    Reads usage_metadata from LlmResponse and logs input/output token counts.
    """
    agent_name = callback_context.agent_name
    usage = llm_response.usage_metadata

    if usage:
        prompt_tokens = usage.prompt_token_count or 0
        output_tokens = usage.candidates_token_count or 0
        cached_tokens = usage.cached_content_token_count or 0
        logger.info(
            "TOKEN_USAGE | agent=%s | input=%d | output=%d | cached=%d | total=%d",
            agent_name,
            prompt_tokens,
            output_tokens,
            cached_tokens,
            prompt_tokens + output_tokens,
        )
    else:
        logger.warning("TOKEN_USAGE | agent=%s | no usage metadata available", agent_name)


def handle_model_error(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
    error: Exception,
) -> LlmResponse | None:
    """Handle LLM errors with flat 60s backoff for rate-limit (429) errors.

    This is wired as on_model_error_callback on slide agents. When a 429 /
    resource_exhausted error is caught, it sleeps 60s (one TPM window) and
    returns a fallback LlmResponse so the agent can retry on the next turn.
    Non-rate-limit errors are re-raised (return None).
    """
    error_text = str(error).lower()
    is_rate_limit = (
        "429" in error_text
        or "resource_exhausted" in error_text
        or "rate limit" in error_text
    )

    if not is_rate_limit:
        logger.error("LLM_ERROR | agent=%s | error=%s", callback_context.agent_name, error)
        return None  # Let ADK re-raise the exception

    # Compute backoff delay
    info = callback_context.state.get(BACKOFF_STATE_KEY, {})
    attempt = int(info.get("attempt", 0)) + 1
    delay = min(
        BACKOFF_MAX_SECONDS,
        BACKOFF_BASE_SECONDS * (BACKOFF_MULTIPLIER ** (attempt - 1)),
    )
    callback_context.state[BACKOFF_STATE_KEY] = {
        "attempt": attempt,
        "until": time.time() + delay,
    }

    logger.warning(
        "RATE_LIMIT | agent=%s | attempt=%d | sleeping %.1fs | error=%s",
        callback_context.agent_name,
        attempt,
        delay,
        error,
    )
    time.sleep(delay)

    # Return a fallback response so the agent retries on the next turn
    return LlmResponse(
        content=genai_types.Content(
            role="model",
            parts=[genai_types.Part.from_text(
                text="Rate limit hit — retrying after backoff. Please continue with the task."
            )],
        ),
    )

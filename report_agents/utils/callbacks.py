"""Callbacks for ADK agent hooks."""

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest
from google.genai import types as genai_types


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


def inject_state_into_prompt(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> None:
    """Replace {parsed_documents} and {parsed_tables_json} placeholders
    in the system instruction with actual values from session state.
    """
    if not llm_request.config or not llm_request.config.system_instruction:
        return

    si = llm_request.config.system_instruction
    state = callback_context.state

    replacements = {
        "{parsed_documents}": state.get("parsed_documents", "")
            or "[No parsed documents found in session state]",
        "{parsed_tables_json}": state.get("parsed_tables_json", "[]"),
    }

    if isinstance(si, str):
        for placeholder, value in replacements.items():
            si = si.replace(placeholder, value)
        llm_request.config.system_instruction = si
    elif hasattr(si, "parts"):
        for part in si.parts:
            if part.text:
                for placeholder, value in replacements.items():
                    part.text = part.text.replace(placeholder, value)


def prepare_slide_request(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> None:
    """Composite callback: strip file parts then inject state into prompt."""
    strip_file_parts(callback_context, llm_request)
    inject_state_into_prompt(callback_context, llm_request)

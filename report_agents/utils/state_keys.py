"""Constants for session state keys used across agents and tools."""

# Input state (set by ingestion)
FULL_DOCUMENT_CONTEXT = "full_document_context"
SUMMARY_DOCUMENT_CONTEXT = "summary_document_context"
PARSED_TABLES_JSON = "parsed_tables_json"


def slide_content_key(n: int) -> str:
    """State key for slide N's markdown content."""
    return f"slide_{n:02d}_content"


def slide_chart_data_key(n: int) -> str:
    """State key for slide N's chart data JSON."""
    return f"slide_{n:02d}_chart_data"


def slide_chart_image_key(n: int) -> str:
    """State key for slide N's chart image artifact filename."""
    return f"slide_{n:02d}_chart_image"

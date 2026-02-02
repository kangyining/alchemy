from google.adk.tools import ToolContext

def initialize_reporting_session(tool_context: ToolContext) -> str:
    """Initialize session state keys for financial reporting to prevent downstream errors.

    Ensures that 'full_document_context' and 'parsed_tables_json'
    exist in the session state with default empty values.
    """
    keys = {
        "full_document_context": "",
        "summary_document_context": "",
        "parsed_tables_json": "[]",
    }
    for k, v in keys.items():
        if k not in tool_context.state:
            tool_context.state[k] = v
    return "Session initialized."

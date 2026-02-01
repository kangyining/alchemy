from google.adk.tools import ToolContext

def initialize_reporting_session(tool_context: ToolContext) -> str:
    """Initialize session state keys for financial reporting to prevent downstream errors.
    
    Ensures that 'parsed_documents', 'parsed_tables_json', and 'document_sources'
    exist in the session state with default empty values.
    """
    keys = {
        "parsed_documents": "", 
        "parsed_tables_json": "[]", 
        "document_sources": []
    }
    for k, v in keys.items():
        if k not in tool_context.state:
            tool_context.state[k] = v
    return "Session initialized."

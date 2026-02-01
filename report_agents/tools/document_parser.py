"""Document parsing tool using Google Cloud Document AI Layout Parser."""

import json
import os

from google.adk.tools import ToolContext
from google.cloud import documentai_v1 as documentai

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("DOCAI_LOCATION", "us")
PROCESSOR_ID = os.environ.get("DOCAI_PROCESSOR_ID", "")

MIME_TYPE_MAP = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".csv": "text/csv",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _get_mime_type(filename: str) -> str:
    """Determine MIME type from file extension."""
    ext = os.path.splitext(filename)[1].lower()
    return MIME_TYPE_MAP.get(ext, "application/octet-stream")


def _extract_table_text(table, document_text: str) -> dict:
    """Extract table content from a Document AI table object."""
    rows = []
    headers = []

    for i, row in enumerate(table.header_rows):
        header_cells = []
        for cell in row.cells:
            text = _get_text_from_layout(cell.layout, document_text).strip()
            header_cells.append(text)
        headers.append(header_cells)

    for row in table.body_rows:
        row_cells = []
        for cell in row.cells:
            text = _get_text_from_layout(cell.layout, document_text).strip()
            row_cells.append(text)
        rows.append(row_cells)

    return {
        "headers": headers,
        "rows": rows,
    }


def _get_text_from_layout(layout, document_text: str) -> str:
    """Extract text content from a layout element using text anchors."""
    text = ""
    for segment in layout.text_anchor.text_segments:
        start = int(segment.start_index)
        end = int(segment.end_index)
        text += document_text[start:end]
    return text


def parse_uploaded_documents(tool_context: ToolContext) -> dict:
    """Parse all uploaded documents using Document AI Layout Parser.

    Reads artifacts from the session, sends each to Document AI Layout Parser,
    and stores the parsed markdown content and table data in session state.

    Returns:
        Summary of parsing results.
    """
    client = documentai.DocumentProcessorServiceClient()
    processor_name = (
        f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{PROCESSOR_ID}"
    )

    artifact_names = tool_context.list_artifacts()
    if not artifact_names:
        return {
            "status": "error",
            "message": "No documents were uploaded. Please upload files first.",
        }

    parsed = {"text_sections": [], "tables": []}
    errors = []

    for name in artifact_names:
        try:
            artifact = tool_context.load_artifact(name)
            file_bytes = artifact.inline_data.data
            mime_type = _get_mime_type(name)

            request = documentai.ProcessRequest(
                name=processor_name,
                raw_document=documentai.RawDocument(
                    content=file_bytes, mime_type=mime_type
                ),
                process_options=documentai.ProcessOptions(
                    layout_config=documentai.ProcessOptions.LayoutConfig(
                        chunking_config=documentai.ProcessOptions.LayoutConfig.ChunkingConfig(
                            chunk_size=1000,
                            include_ancestor_headings=True,
                        )
                    )
                ),
            )
            result = client.process_document(request=request)
            document = result.document

            # Extract markdown chunks from Layout Parser
            if document.chunked_document and document.chunked_document.chunks:
                for chunk in document.chunked_document.chunks:
                    parsed["text_sections"].append(
                        {
                            "source": name,
                            "content": chunk.content,
                        }
                    )
            elif document.text:
                # Fallback: if no chunks, use the full document text
                parsed["text_sections"].append(
                    {
                        "source": name,
                        "content": document.text,
                    }
                )

            # Extract tables separately for chart agents
            for page in document.pages:
                for table in page.tables:
                    table_data = _extract_table_text(table, document.text)
                    table_data["source"] = name
                    table_data["page"] = page.page_number
                    parsed["tables"].append(table_data)

        except Exception as e:
            errors.append({"file": name, "error": str(e)})

    # Build a single concatenated text for agents to consume
    all_text_parts = []
    for section in parsed["text_sections"]:
        all_text_parts.append(f"--- Source: {section['source']} ---\n{section['content']}")
    parsed["full_text"] = "\n\n".join(all_text_parts)

    # Store in session state
    tool_context.state["parsed_documents"] = parsed["full_text"]
    tool_context.state["parsed_tables_json"] = json.dumps(parsed["tables"], default=str)
    tool_context.state["document_sources"] = [name for name in artifact_names]

    return {
        "status": "success",
        "documents_parsed": len(artifact_names) - len(errors),
        "text_sections": len(parsed["text_sections"]),
        "tables_found": len(parsed["tables"]),
        "errors": errors if errors else None,
    }

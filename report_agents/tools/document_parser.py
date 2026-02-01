"""Document parsing using Google Cloud Document AI Layout Parser."""

import asyncio
import json
import os
from typing import Optional

from dotenv import load_dotenv
from google.cloud import documentai_v1 as documentai
from google.genai import types as genai_types

load_dotenv()

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


def _collect_inline_files(
    user_content: Optional[genai_types.Content],
) -> list[tuple[str, bytes, str]]:
    """Extract inline file parts from user message content.

    ADK web sends uploaded files as inline_data parts rather than artifacts.
    Returns list of (filename, data_bytes, mime_type) tuples.
    """
    files = []
    if not user_content or not user_content.parts:
        return files

    ext_map = {v: k for k, v in MIME_TYPE_MAP.items()}
    for i, part in enumerate(user_content.parts):
        if part.inline_data and part.inline_data.data:
            mime = part.inline_data.mime_type or "application/octet-stream"
            ext = ext_map.get(mime, ".bin")
            name = f"upload_{i}{ext}"
            files.append((name, part.inline_data.data, mime))
    return files


async def parse_documents(
    files: list[tuple[str, bytes, str]],
) -> dict:
    """Parse documents using Document AI Layout Parser.

    Args:
        files: List of (filename, raw_bytes, mime_type) tuples.

    Returns:
        Dict with keys: status, parsed_documents, parsed_tables_json,
        document_sources, documents_parsed, text_sections, tables_found, errors.
    """
    if not files:
        return {
            "status": "error",
            "message": "No documents were detected. Please upload files first.",
            "parsed_documents": "",
            "parsed_tables_json": "[]",
            "document_sources": [],
        }

    client = documentai.DocumentProcessorServiceClient()
    processor_name = (
        f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{PROCESSOR_ID}"
    )

    parsed = {"text_sections": [], "tables": []}
    errors = []

    for name, file_bytes, mime_type in files:
        try:
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
            result = await asyncio.to_thread(client.process_document, request=request)
            document = result.document

            # Extract markdown chunks from Layout Parser
            if document.chunked_document and document.chunked_document.chunks:
                for chunk in document.chunked_document.chunks:
                    parsed["text_sections"].append(
                        {"source": name, "content": chunk.content}
                    )
            elif document.text:
                parsed["text_sections"].append(
                    {"source": name, "content": document.text}
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

    # Build concatenated text
    all_text_parts = []
    for section in parsed["text_sections"]:
        all_text_parts.append(
            f"--- Source: {section['source']} ---\n{section['content']}"
        )
    full_text = "\n\n".join(all_text_parts)

    return {
        "status": "success",
        "parsed_documents": full_text,
        "parsed_tables_json": json.dumps(parsed["tables"], default=str),
        "document_sources": [name for name, _, _ in files],
        "documents_parsed": len(files) - len(errors),
        "text_sections": len(parsed["text_sections"]),
        "tables_found": len(parsed["tables"]),
        "errors": errors if errors else None,
    }

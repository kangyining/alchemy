"""Document parsing using Google Cloud Document AI Layout Parser."""

import asyncio
import io
import json
import logging
import os
import re
from typing import Optional

from dotenv import load_dotenv
from google.cloud import documentai_v1 as documentai
from google.genai import types as genai_types
from pypdf import PdfReader, PdfWriter

load_dotenv()

logger = logging.getLogger(__name__)

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("DOCAI_LOCATION", "us")
PROCESSOR_ID = os.environ.get("DOCAI_PROCESSOR_ID", "")

# Document AI online API page limit per request.
_DOCAI_MAX_PAGES = 15

# Max concurrent Document AI requests (1 = sequential to avoid server-side throttling)
_DOCAI_MAX_CONCURRENCY = 1

# Seconds to wait between sequential Document AI requests (rate limit spacing)
_DOCAI_INTER_REQUEST_DELAY = 5.0

_docai_client: documentai.DocumentProcessorServiceClient | None = None


def _get_docai_client() -> documentai.DocumentProcessorServiceClient:
    """Get or create a cached Document AI client."""
    global _docai_client
    if _docai_client is None:
        _docai_client = documentai.DocumentProcessorServiceClient()
    return _docai_client


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


def _split_pdf(
    filename: str, pdf_bytes: bytes,
) -> list[tuple[str, bytes]]:
    """Split a PDF into chunks of at most _DOCAI_MAX_PAGES pages.

    Returns a list of (chunk_name, chunk_bytes) tuples.  If the PDF is
    already within the page limit, it is returned as-is (single element list).
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(reader.pages)

    if total_pages <= _DOCAI_MAX_PAGES:
        return [(filename, pdf_bytes)]

    chunks: list[tuple[str, bytes]] = []
    for start in range(0, total_pages, _DOCAI_MAX_PAGES):
        end = min(start + _DOCAI_MAX_PAGES, total_pages)
        writer = PdfWriter()
        for page_idx in range(start, end):
            writer.add_page(reader.pages[page_idx])
        buf = io.BytesIO()
        writer.write(buf)
        chunk_name = f"{filename}_pages_{start + 1}-{end}"
        chunks.append((chunk_name, buf.getvalue()))

    logger.info(
        "Split %s (%d pages) into %d chunks of <=%d pages",
        filename, total_pages, len(chunks), _DOCAI_MAX_PAGES,
    )
    return chunks


def _original_source(chunk_name: str) -> str:
    """Map a chunk name back to the original filename.

    'report.pdf_pages_1-15' -> 'report.pdf'
    'report.pdf'            -> 'report.pdf'
    """
    return re.sub(r"_pages_\d+-\d+$", "", chunk_name)


async def _process_single_file(
    name: str,
    file_bytes: bytes,
    mime_type: str,
    processor_name: str,
    client: documentai.DocumentProcessorServiceClient,
    semaphore: asyncio.Semaphore,
    is_first: bool = True,
) -> tuple[list[dict], list[dict], dict | None]:
    """Process a single file through Document AI.

    Returns (text_sections, tables, error_or_none).
    Uses a semaphore to limit concurrent requests.
    Adds a delay before non-first requests to respect rate limits.
    """
    source = _original_source(name)
    async with semaphore:
        if not is_first and _DOCAI_INTER_REQUEST_DELAY > 0:
            logger.info("Waiting %.1fs before next Document AI request...", _DOCAI_INTER_REQUEST_DELAY)
            await asyncio.sleep(_DOCAI_INTER_REQUEST_DELAY)
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
            result = await asyncio.to_thread(
                client.process_document, request=request, timeout=600.0
            )
            document = result.document

            text_sections: list[dict] = []
            if document.chunked_document and document.chunked_document.chunks:
                for chunk in document.chunked_document.chunks:
                    text_sections.append({"source": source, "content": chunk.content})
            elif document.text:
                text_sections.append({"source": source, "content": document.text})

            tables: list[dict] = []
            for page in document.pages:
                for table in page.tables:
                    table_data = _extract_table_text(table, document.text)
                    table_data["source"] = source
                    table_data["page"] = page.page_number
                    tables.append(table_data)

            return text_sections, tables, None

        except Exception as e:
            logger.error("Failed to parse %s: %s", name, e)
            return [], [], {"file": name, "error": str(e)}


async def parse_documents(
    files: list[tuple[str, bytes, str]],
) -> dict:
    """Parse documents using Document AI Layout Parser.

    PDFs over 15 pages are split into chunks.  All files and chunks are
    processed in parallel via asyncio.gather.

    Args:
        files: List of (filename, raw_bytes, mime_type) tuples.

    Returns:
        Dict with keys: status, full_document_context, parsed_tables_json,
        documents_parsed, text_sections, tables_found, errors.
    """
    if not files:
        return {
            "status": "error",
            "message": "No documents were detected. Please upload files first.",
            "full_document_context": "",
            "summary_document_context": "",
            "parsed_tables_json": "[]",
        }

    client = _get_docai_client()
    processor_name = (
        f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{PROCESSOR_ID}"
    )

    # 1. Split large PDFs into <=15-page chunks; non-PDFs pass through
    expanded_files: list[tuple[str, bytes, str]] = []
    for name, file_bytes, mime_type in files:
        if mime_type == "application/pdf":
            for chunk_name, chunk_bytes in _split_pdf(name, file_bytes):
                expanded_files.append((chunk_name, chunk_bytes, mime_type))
        else:
            expanded_files.append((name, file_bytes, mime_type))

    logger.info(
        "Processing %d file(s) / chunk(s) in parallel: %s",
        len(expanded_files), [f[0] for f in expanded_files],
    )

    # 2. Process all files/chunks in parallel (with concurrency limit)
    semaphore = asyncio.Semaphore(_DOCAI_MAX_CONCURRENCY)
    tasks = [
        _process_single_file(name, data, mime, processor_name, client, semaphore, is_first=(i == 0))
        for i, (name, data, mime) in enumerate(expanded_files)
    ]
    results = await asyncio.gather(*tasks)

    # 3. Merge results
    all_text_sections: list[dict] = []
    all_tables: list[dict] = []
    errors: list[dict] = []

    for text_sections, tables, error in results:
        all_text_sections.extend(text_sections)
        all_tables.extend(tables)
        if error:
            errors.append(error)

    # Build full formatted document context string
    full_document_context = _build_full_document_context(
        all_text_sections, all_tables
    )
    # Build shorter summary context for TEXT-only slides (cover, exec summary, outlook)
    summary_document_context = _build_summary_document_context(
        all_text_sections
    )

    return {
        "status": "success",
        "full_document_context": full_document_context,
        "summary_document_context": summary_document_context,
        "parsed_tables_json": json.dumps(all_tables, default=str),
        "documents_parsed": len(files) - len(errors),
        "text_sections": len(all_text_sections),
        "tables_found": len(all_tables),
        "errors": errors if errors else None,
    }


def _build_full_document_context(
    text_sections: list[dict], tables: list[dict]
) -> str:
    """Build a formatted markdown string from text sections and tables.

    Groups text by source file and renders tables as markdown.
    This is built once during ingestion and stored in state for slide agents.
    """
    if not text_sections and not tables:
        return ""

    parts: list[str] = ["## SOURCE DOCUMENTS\n"]

    # Group text sections by source file
    by_source: dict[str, list[str]] = {}
    for section in text_sections:
        src = section.get("source", "unknown")
        by_source.setdefault(src, []).append(section.get("content", ""))

    for src, contents in by_source.items():
        parts.append(f"### {src}\n")
        parts.extend(contents)
        parts.append("")

    # Render tables as markdown
    if tables:
        parts.append("## EXTRACTED TABLES\n")
        for i, table in enumerate(tables):
            src = table.get("source", "unknown")
            headers = table.get("headers", [])
            rows = table.get("rows", [])
            parts.append(f"### Table {i + 1} (from {src})")
            if headers:
                header_row = headers[0] if headers else []
                if header_row:
                    parts.append("| " + " | ".join(header_row) + " |")
                    parts.append("| " + " | ".join("---" for _ in header_row) + " |")
            for row in rows:
                parts.append("| " + " | ".join(row) + " |")
            parts.append("")

    return "\n".join(parts)


# Maximum text sections per source file to include in the summary context.
_SUMMARY_MAX_SECTIONS_PER_SOURCE = 3


def _build_summary_document_context(text_sections: list[dict]) -> str:
    """Build a shorter document context with only the first few text sections.

    Used for TEXT-only slides (Cover, Executive Summary, Outlook) that don't
    need full financial tables or deep detail — just company name, period,
    key highlights, and forward-looking statements.  Skips tables entirely.
    """
    if not text_sections:
        return ""

    parts: list[str] = ["## SOURCE DOCUMENTS (SUMMARY)\n"]

    by_source: dict[str, list[str]] = {}
    for section in text_sections:
        src = section.get("source", "unknown")
        by_source.setdefault(src, []).append(section.get("content", ""))

    for src, contents in by_source.items():
        parts.append(f"### {src}\n")
        parts.extend(contents[:_SUMMARY_MAX_SECTIONS_PER_SOURCE])
        if len(contents) > _SUMMARY_MAX_SECTIONS_PER_SOURCE:
            parts.append(f"\n[... {len(contents) - _SUMMARY_MAX_SECTIONS_PER_SOURCE} more sections omitted ...]")
        parts.append("")

    return "\n".join(parts)

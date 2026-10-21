"""Document parsing using Google Cloud Document AI Layout Parser."""

import asyncio
import io
import json
import logging
import os
import re
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.cloud import documentai_v1 as documentai
from google.genai import types as genai_types
from PIL import Image
from pptx import Presentation
from pptx.shapes.picture import Picture
from pypdf import PdfReader, PdfWriter

from report_agents.utils.gemini_models import GEMINI_MODEL

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

# Directory to dump parsed output for debugging (set to "" to disable)
_DEBUG_DUMP_DIR = os.environ.get("DOCAI_DEBUG_DUMP_DIR", "")  # disabled by default

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


def _is_empty_row(row: list) -> bool:
    """Check if a row is entirely empty or NaN values."""
    for cell in row:
        if cell is None:
            continue
        s = str(cell).strip().lower()
        if s and s not in ("", "nan", "none", "nat"):
            return False
    return True


def _escape_csv_cell(value: str) -> str:
    """Escape a CSV cell value if it contains commas, quotes, or newlines."""
    if "," in value or '"' in value or "\n" in value:
        # Escape double quotes by doubling them, then wrap in quotes
        return '"' + value.replace('"', '""') + '"'
    return value


def _rows_to_csv(headers: list[str], rows: list[list]) -> str:
    """Convert headers and rows to a compact CSV string.

    This reduces token count significantly compared to JSON list-of-lists
    by eliminating repeated brackets and quotes.
    Properly escapes cells containing commas, quotes, or newlines.
    """
    lines = [",".join(_escape_csv_cell(str(h)) for h in headers)]
    for row in rows:
        lines.append(",".join(_escape_csv_cell(str(cell)) for cell in row))
    return "\n".join(lines)


def _sanitize_column_names(columns: list) -> list[str]:
    """Minimally clean column names for SQLite-friendly schemas.

    - Replace empty/Unnamed/NaN headers with generated names
    - Replace non-alphanumeric chars with underscores
    - Ensure names are unique and don't start with digits
    """
    cleaned: list[str] = []
    seen: dict[str, int] = {}
    for idx, col in enumerate(columns):
        name = str(col).strip()
        lower = name.lower()
        if not name or lower.startswith("unnamed:") or lower in ("nan", "none"):
            name = f"col_{idx + 1}"
        name = re.sub(r"[^a-zA-Z0-9]", "_", name)
        name = re.sub(r"_+", "_", name).strip("_")
        if not name:
            name = f"col_{idx + 1}"
        name = name.lower()
        if name[0].isdigit():
            name = f"col_{name}"
        count = seen.get(name, 0) + 1
        seen[name] = count
        if count > 1:
            name = f"{name}_{count}"
        cleaned.append(name)
    return cleaned


def _extract_table_text(table, document_text: str) -> dict:
    """Extract table content from a Document AI table object.

    Uses optimized CSV format for rows to reduce token count.
    Empty rows are filtered out.
    """
    rows = []
    headers = []

    for row in table.header_rows:
        header_cells = []
        for cell in row.cells:
            text = _get_text_from_layout(cell.layout, document_text).strip()
            header_cells.append(text)
        if header_cells:
            headers = header_cells  # Use last header row as the header
            break  # Typically only one header row

    for row in table.body_rows:
        row_cells = []
        for cell in row.cells:
            text = _get_text_from_layout(cell.layout, document_text).strip()
            row_cells.append(text)
        # Filter out empty rows
        if not _is_empty_row(row_cells):
            rows.append(row_cells)

    return {
        "headers": headers,
        "rows_csv": _rows_to_csv(headers, rows) if headers else "",
        "row_count": len(rows),
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
            display_name = None
            if getattr(part.inline_data, "display_name", None):
                display_name = part.inline_data.display_name
            elif getattr(part, "file_data", None) and getattr(part.file_data, "display_name", None):
                display_name = part.file_data.display_name
            elif getattr(part, "file_data", None) and getattr(part.file_data, "file_uri", None):
                display_name = os.path.basename(part.file_data.file_uri)

            if display_name:
                name = os.path.basename(display_name)
                if not os.path.splitext(name)[1]:
                    name = f"{name}{ext}"
            else:
                name = f"upload_{i}{ext}"
            files.append((name, part.inline_data.data, mime))
    return files


# ---------------------------------------------------------------------------
# Unit multiplier detection for financial spreadsheets
# ---------------------------------------------------------------------------
# Financial Excel files often express dollar values with a unit qualifier
# (e.g., "($ in thousands)") in sheet names, column headers, or early rows.
# We detect these per-sheet and surface them as metadata so downstream LLM
# agents can apply the correct multiplier in SQL queries.
_UNIT_PATTERNS: list[tuple[re.Pattern, int, str]] = [
    (re.compile(r"in\s+thousands", re.IGNORECASE), 1_000, "thousands"),
    (re.compile(r"in\s+millions", re.IGNORECASE), 1_000_000, "millions"),
    (re.compile(r"in\s+billions", re.IGNORECASE), 1_000_000_000, "billions"),
]

# Number of initial rows to scan for unit qualifiers
_UNIT_SCAN_ROWS = 10


def _detect_unit_multiplier(
    sheet_name: str, df: pd.DataFrame,
) -> dict:
    """Detect unit multiplier from sheet name, column headers, and first rows.

    Scans per-sheet (each sheet in a workbook can have different units).

    Returns:
        Dict with keys: multiplier (int), unit_label (str), note (str).
        If no unit qualifier is detected, multiplier=1 and note="".
    """

    def _match(text: str) -> dict | None:
        for pattern, multiplier, label in _UNIT_PATTERNS:
            if pattern.search(text):
                return {
                    "multiplier": multiplier,
                    "unit_label": label,
                    "note": f"Values expressed in {label} (multiply by {multiplier:,} for actual amounts)",
                }
        return None

    # 1. Check sheet name
    result = _match(sheet_name)
    if result:
        return result

    # 2. Check column headers
    for col in df.columns:
        col_str = str(col)
        result = _match(col_str)
        if result:
            return result

    # 3. Check first N rows (cell values converted to string)
    scan_rows = df.head(_UNIT_SCAN_ROWS)
    for _, row in scan_rows.iterrows():
        for cell in row:
            cell_str = str(cell).strip()
            if cell_str and cell_str.lower() not in ("", "nan", "none", "nat"):
                result = _match(cell_str)
                if result:
                    return result

    return {"multiplier": 1, "unit_label": "", "note": ""}


# MIME types that should be parsed natively (not sent to Document AI)
_SPREADSHEET_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/vnd.ms-excel",  # .xls
    "text/csv",
}

# MIME types that should be parsed via native PPTX parser + Gemini Vision
_PPTX_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # .pptx
}

# Max concurrent Gemini Vision requests for slide images
_PPTX_VISION_MAX_CONCURRENCY = 5

# Prompt sent to Gemini Flash for each slide image
_PPTX_VISION_PROMPT = (
    "Extract ALL visible text from this presentation slide image. "
    "Include titles, subtitles, bullet points, labels, footnotes, "
    "and any text inside charts or tables. "
    "For tables, reproduce them in markdown table format. "
    "For charts, describe the data series, values, and axis labels. "
    "Return only the extracted content, no commentary."
)

# Max megapixels before downscaling slide images for Gemini
_PPTX_IMAGE_MAX_MEGAPIXELS = 4

# Max rows per sheet to include in markdown output (prevent token explosion)
_MAX_ROWS_PER_SHEET = 1500


def _parse_spreadsheet(
    name: str, file_bytes: bytes, mime_type: str,
) -> tuple[list[dict], list[dict], dict[str, pd.DataFrame], dict[str, str]]:
    """Parse Excel/CSV files natively using pandas.

    Returns (text_sections, tables, dataframes, unit_notes) where:
    - text_sections: CSV text for context injection (legacy)
    - tables: Structured table entries (legacy)
    - dataframes: Raw DataFrames for SQLite storage
    - unit_notes: Per-sheet unit notes (keyed by same source:sheet key as dataframes)

    Optimizations applied to the context-only copy (SQLite stores full data):
    - Floats rounded to 2 decimal places (standard financial precision)
    - Whole numbers converted to int (removes .00 suffix)
    - NaN values replaced with empty strings
    - Duplicate rows removed
    - Empty columns removed (all values empty)
    - Empty rows removed (all values empty)
    - "Unnamed:" headers cleaned to empty strings
    - Tables stored as CSV (50% fewer tokens than markdown tables)
    """
    text_sections: list[dict] = []
    tables: list[dict] = []
    dataframes: dict[str, pd.DataFrame] = {}
    unit_notes: dict[str, str] = {}

    try:
        if mime_type == "text/csv":
            df = pd.read_csv(io.BytesIO(file_bytes))
            sheets = {"Sheet1": df}
        else:
            sheets = pd.read_excel(
                io.BytesIO(file_bytes), sheet_name=None, engine="openpyxl"
            )

        for sheet_name, df in sheets.items():
            if df.empty:
                continue

            # Detect unit multiplier (e.g., "$ in thousands") before sanitization
            unit_info = _detect_unit_multiplier(sheet_name, df)
            if unit_info["note"]:
                logger.info(
                    "Detected unit multiplier for %s/%s: %s",
                    name, sheet_name, unit_info["note"],
                )

            # Store full, untruncated data in SQLite (minimal header cleanup only)
            df_sql = df.copy()
            df_sql.columns = _sanitize_column_names(df_sql.columns)

            truncated = len(df_sql) > _MAX_ROWS_PER_SHEET
            df_display = df_sql.head(_MAX_ROWS_PER_SHEET)

            # Apply token-saving optimizations to the display dataframe:
            # - Round floats to 2 decimal places
            # - Convert whole numbers to int (removes .0 or .00)
            # - Fill NaN with empty strings
            # - Clean "Unnamed:" column headers
            # - Remove empty columns (all values empty)
            # - Remove empty rows (all values empty)
            # - Remove duplicate rows
            df_optimized = df_display.copy()
            for col in df_optimized.select_dtypes(include=["float", "float64"]).columns:
                df_optimized[col] = df_optimized[col].round(2)
                # Convert to int where possible (removes .0 suffix)
                if df_optimized[col].dropna().apply(lambda x: x == int(x) if pd.notna(x) else True).all():
                    df_optimized[col] = df_optimized[col].fillna(0).astype(int).replace(0, pd.NA)
            df_optimized = df_optimized.fillna("")
            # Remove duplicate rows
            df_optimized = df_optimized.drop_duplicates()

            # Remove empty columns (where all values are empty string)
            non_empty_cols = [
                col for col in df_optimized.columns
                if df_optimized[col].astype(str).str.strip().any()
            ]
            df_optimized = df_optimized[non_empty_cols]

            # Remove empty rows (where all values are empty string)
            df_optimized = df_optimized[
                df_optimized.astype(str).apply(
                    lambda row: row.str.strip().any(), axis=1
                )
            ]

            # Clean "Unnamed:" column headers
            df_optimized.columns = [
                "" if str(c).startswith("Unnamed:") else c
                for c in df_optimized.columns
            ]

            # Skip sheet if completely empty after filtering
            if df_optimized.empty:
                continue

            # Store full DataFrame for SQLite (minimal header cleanup only)
            dataframes[sheet_name] = df_sql.copy()
            if unit_info["note"]:
                unit_notes[sheet_name] = unit_info["note"]

            # Build CSV table for text context (more compact than markdown)
            csv_content = f"[Sheet: {sheet_name}]\n"
            csv_content += df_optimized.to_csv(index=False)
            if truncated:
                csv_content += f"\n[... {len(df) - _MAX_ROWS_PER_SHEET} more rows truncated ...]"
            csv_content += "\n"

            text_sections.append({"source": name, "content": csv_content})

            # Build structured table entry (reuse optimized dataframe)
            # Optimizations already applied: rounded floats, NaN->empty, clean headers
            # Additional: filter empty rows, store as CSV string
            headers = list(df_optimized.columns.astype(str))
            all_rows = df_optimized.astype(str).values.tolist()
            filtered_rows = [row for row in all_rows if not _is_empty_row(row)]

            tables.append({
                "source": name,
                "sheet": sheet_name,
                "headers": headers,
                "rows_csv": _rows_to_csv(headers, filtered_rows),
                "row_count": len(filtered_rows),
            })

        logger.info(
            "Parsed spreadsheet %s: %d sheet(s), %d total row(s)",
            name, len(sheets), sum(len(df) for df in sheets.values()),
        )

    except Exception as e:
        logger.error("Failed to parse spreadsheet %s: %s", name, e)

    return text_sections, tables, dataframes, unit_notes


# ---------------------------------------------------------------------------
# PPTX native parsing with Gemini Vision
# ---------------------------------------------------------------------------


def _extract_slide_content(
    slide, slide_index: int,
) -> tuple[str, list[tuple[bytes, str]]]:
    """Extract text and images from a single PPTX slide.

    Returns (text, list_of_(image_bytes, mime_type) tuples).
    Skips images smaller than 1 KB (icons/decorations).
    """
    text_parts: list[str] = []
    images: list[tuple[bytes, str]] = []

    for shape in slide.shapes:
        # Extract text from text frames
        if shape.has_text_frame:
            for paragraph in shape.text_frame.paragraphs:
                line = paragraph.text.strip()
                if line:
                    text_parts.append(line)

        # Extract images from Picture shapes
        if isinstance(shape, Picture):
            image_blob = shape.image.blob
            if len(image_blob) < 1024:
                continue  # Skip tiny icons/decorations
            content_type = shape.image.content_type or "image/png"
            images.append((image_blob, content_type))

    return "\n".join(text_parts), images


def _maybe_resize_image(image_bytes: bytes, mime_type: str) -> tuple[bytes, str]:
    """Downscale image if it exceeds _PPTX_IMAGE_MAX_MEGAPIXELS.

    Returns (possibly resized bytes, mime_type).
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        megapixels = (img.width * img.height) / 1_000_000
        if megapixels <= _PPTX_IMAGE_MAX_MEGAPIXELS:
            return image_bytes, mime_type
        scale = (_PPTX_IMAGE_MAX_MEGAPIXELS / megapixels) ** 0.5
        new_w = int(img.width * scale)
        new_h = int(img.height * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue(), "image/png"
    except Exception:
        return image_bytes, mime_type


async def _describe_image_with_vision(
    image_bytes: bytes,
    mime_type: str,
    slide_index: int,
    semaphore: asyncio.Semaphore,
) -> str:
    """Send a slide image to Gemini Flash vision and return extracted text."""
    async with semaphore:
        try:
            image_bytes, mime_type = _maybe_resize_image(image_bytes, mime_type)
            client = genai.Client()
            response = await client.aio.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    _PPTX_VISION_PROMPT,
                ],
            )
            return response.text or ""
        except Exception as e:
            logger.warning(
                "Gemini vision failed for slide %d image: %s", slide_index + 1, e,
            )
            return ""


async def _parse_pptx(
    name: str, file_bytes: bytes,
) -> tuple[list[dict], list[dict], dict[str, pd.DataFrame], dict[str, str]]:
    """Parse a PPTX file using python-pptx + Gemini Flash vision.

    Phase 1: Extract direct text and images from all slides (sync, fast).
    Phase 2: Send images to Gemini Vision concurrently.
    Phase 3: Combine results into text_sections.

    Returns (text_sections, [], {}, {}) — same 4-tuple as _parse_spreadsheet.
    """
    text_sections: list[dict] = []

    try:
        prs = Presentation(io.BytesIO(file_bytes))
    except Exception as e:
        logger.error("Failed to open PPTX %s: %s", name, e)
        return text_sections, [], {}, {}

    # Phase 1: extract text + images from each slide
    slide_data: list[tuple[str, list[tuple[bytes, str]]]] = []
    total_images = 0
    for i, slide in enumerate(prs.slides):
        text, images = _extract_slide_content(slide, i)
        slide_data.append((text, images))
        total_images += len(images)

    # Phase 2: send all images to Gemini Vision concurrently
    semaphore = asyncio.Semaphore(_PPTX_VISION_MAX_CONCURRENCY)
    vision_tasks: list[tuple[int, int, asyncio.Task]] = []  # (slide_idx, img_idx, task)
    for slide_idx, (_, images) in enumerate(slide_data):
        for img_idx, (img_bytes, img_mime) in enumerate(images):
            task = asyncio.create_task(
                _describe_image_with_vision(img_bytes, img_mime, slide_idx, semaphore)
            )
            vision_tasks.append((slide_idx, img_idx, task))

    vision_results: dict[int, list[str]] = {}
    if vision_tasks:
        results = await asyncio.gather(*(t for _, _, t in vision_tasks))
        for (slide_idx, _, _), result_text in zip(vision_tasks, results):
            vision_results.setdefault(slide_idx, []).append(result_text)

    # Phase 3: combine direct text + vision text per slide
    for slide_idx, (direct_text, _) in enumerate(slide_data):
        parts: list[str] = []
        if direct_text:
            parts.append(direct_text)
        for vision_text in vision_results.get(slide_idx, []):
            if vision_text.strip():
                parts.append(vision_text.strip())

        if parts:
            content = f"[Slide {slide_idx + 1}]\n" + "\n".join(parts)
            text_sections.append({"source": name, "content": content})

    images_processed = sum(1 for r in results if r.strip()) if vision_tasks else 0
    logger.info(
        "Parsed PPTX %s: %d slide(s), %d text section(s), %d images processed via vision",
        name, len(prs.slides), len(text_sections), images_processed,
    )

    return text_sections, [], {}, {}


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

            # Debug: log what Document AI returned
            num_pages = len(document.pages) if document.pages else 0
            text_len = len(document.text) if document.text else 0
            num_chunks = len(document.chunked_document.chunks) if document.chunked_document and document.chunked_document.chunks else 0
            logger.info(
                "DocAI response for %s: pages=%d, text_len=%d, chunks=%d, mime=%s",
                name, num_pages, text_len, num_chunks, mime_type,
            )
            if num_pages == 0 and text_len == 0:
                logger.warning(
                    "DocAI returned empty content for %s — file may contain only images/graphics",
                    name,
                )

            text_sections: list[dict] = []
            if document.chunked_document and document.chunked_document.chunks:
                for chunk in document.chunked_document.chunks:
                    text_sections.append({"source": source, "content": chunk.content})
            elif document.text:
                text_sections.append({"source": source, "content": document.text})

            # Note: When using Layout Parser with chunking_config, tables are
            # embedded as markdown within the text chunks above. The structured
            # document.pages[].tables field is not populated in this mode.
            # We still attempt extraction as a fallback for non-chunked responses.
            tables: list[dict] = []
            if not (document.chunked_document and document.chunked_document.chunks):
                for page in document.pages:
                    for table in page.tables:
                        table_data = _extract_table_text(table, document.text)
                        table_data["source"] = source
                        table_data["page"] = page.page_number
                        tables.append(table_data)

            logger.info(
                "Parsed %s: %d text section(s), %d table(s)",
                name, len(text_sections), len(tables),
            )
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

    # 1. Separate files by parser: spreadsheets (pandas), PPTX (native+vision), rest (Document AI)
    docai_files: list[tuple[str, bytes, str]] = []
    spreadsheet_files: list[tuple[str, bytes, str]] = []
    pptx_files: list[tuple[str, bytes, str]] = []
    for name, file_bytes, mime_type in files:
        logger.info("Routing file %s (mime=%s, size=%d bytes)", name, mime_type, len(file_bytes))
        if mime_type in _SPREADSHEET_MIME_TYPES:
            spreadsheet_files.append((name, file_bytes, mime_type))
        elif mime_type in _PPTX_MIME_TYPES:
            pptx_files.append((name, file_bytes, mime_type))
        else:
            docai_files.append((name, file_bytes, mime_type))

    all_text_sections: list[dict] = []
    all_tables: list[dict] = []
    all_dataframes: dict[str, pd.DataFrame] = {}  # source_file:sheet_name -> DataFrame
    all_unit_notes: dict[str, str] = {}  # source_file:sheet_name -> unit note
    errors: list[dict] = []

    # 2a. Parse spreadsheets natively (no Document AI cost, full sheet support)
    for name, file_bytes, mime_type in spreadsheet_files:
        text_sections, tables, dataframes, unit_notes = _parse_spreadsheet(name, file_bytes, mime_type)
        all_text_sections.extend(text_sections)
        all_tables.extend(tables)
        # Store dataframes and unit notes with composite key (source:sheet)
        for sheet_name, df in dataframes.items():
            key = f"{name}:{sheet_name}"
            all_dataframes[key] = df
            if sheet_name in unit_notes:
                all_unit_notes[key] = unit_notes[sheet_name]

    # 2b. Parse PPTX files natively with Gemini Vision
    for name, file_bytes, mime_type in pptx_files:
        text_sections, tables, dataframes, unit_notes = await _parse_pptx(name, file_bytes)
        all_text_sections.extend(text_sections)
        all_tables.extend(tables)

    # 2c. Process remaining files via Document AI
    if docai_files:
        client = _get_docai_client()
        processor_name = (
            f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{PROCESSOR_ID}"
        )

        # Split large PDFs into <=15-page chunks; non-PDFs pass through
        expanded_files: list[tuple[str, bytes, str]] = []
        for name, file_bytes, mime_type in docai_files:
            if mime_type == "application/pdf":
                for chunk_name, chunk_bytes in _split_pdf(name, file_bytes):
                    expanded_files.append((chunk_name, chunk_bytes, mime_type))
            else:
                expanded_files.append((name, file_bytes, mime_type))

        logger.info(
            "Sending %d file(s) / chunk(s) to Document AI: %s",
            len(expanded_files), [f[0] for f in expanded_files],
        )

        semaphore = asyncio.Semaphore(_DOCAI_MAX_CONCURRENCY)
        tasks = [
            _process_single_file(name, data, mime, processor_name, client, semaphore, is_first=(i == 0))
            for i, (name, data, mime) in enumerate(expanded_files)
        ]
        results = await asyncio.gather(*tasks)

        for text_sections, tables, error in results:
            all_text_sections.extend(text_sections)
            all_tables.extend(tables)
            if error:
                errors.append(error)

    # Build full formatted document context string
    full_document_context = _build_full_document_context(
        all_text_sections, all_tables
    )
    # Build full text-only context (non-spreadsheet sources) for FULL slides
    full_text_document_context = _build_full_text_document_context(
        all_text_sections
    )
    # Build shorter summary context for TEXT-only slides (cover, exec summary, outlook)
    summary_document_context = _build_summary_document_context(
        all_text_sections
    )

    # Debug dump: save parsed output locally for inspection
    if _DEBUG_DUMP_DIR:
        try:
            os.makedirs(_DEBUG_DUMP_DIR, exist_ok=True)
            with open(os.path.join(_DEBUG_DUMP_DIR, "full_document_context.md"), "w") as f:
                f.write(full_document_context)
            with open(os.path.join(_DEBUG_DUMP_DIR, "summary_document_context.md"), "w") as f:
                f.write(summary_document_context)
            with open(os.path.join(_DEBUG_DUMP_DIR, "parsed_tables.json"), "w") as f:
                json.dump(all_tables, f, indent=2, default=str)
            with open(os.path.join(_DEBUG_DUMP_DIR, "text_sections.json"), "w") as f:
                json.dump(all_text_sections, f, indent=2, default=str)
            logger.info("Debug output saved to %s/", _DEBUG_DUMP_DIR)
        except Exception as e:
            logger.warning("Failed to write debug output: %s", e)

    return {
        "status": "success",
        "full_document_context": full_document_context,
        "full_text_document_context": full_text_document_context,
        "summary_document_context": summary_document_context,
        "parsed_tables_json": json.dumps(all_tables, default=str),
        "dataframes": all_dataframes,  # raw DataFrames for SQLite storage
        "unit_notes": all_unit_notes,  # per-sheet unit notes (e.g., "Values expressed in thousands")
        "documents_parsed": len(files) - len(errors),
        "text_sections": len(all_text_sections),
        "tables_found": len(all_tables),
        "errors": errors if errors else None,
    }


def _build_full_document_context(
    text_sections: list[dict], tables: list[dict]
) -> str:
    """Build a formatted markdown string from text sections.

    Groups text by source file. Tables are already embedded as markdown
    within text_sections (from df.to_markdown() for spreadsheets, or
    within Document AI chunks for PDFs), so we don't render them separately.

    The `tables` parameter is kept for API compatibility but not used.
    """
    if not text_sections:
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

    return "\n".join(parts)


# Maximum text sections per source file to include in the summary context.
_SUMMARY_MAX_SECTIONS_PER_SOURCE = 10


def _build_summary_document_context(text_sections: list[dict]) -> str:
    """Build a shorter document context for high-level slides.

    Used for Cover and Outlook slides that only need company name, period,
    and key highlights — not detailed financial tables.

    Skips spreadsheet sources entirely (xlsx, xls, csv) since those contain
    table data. Only includes PDF/document text sections.
    """
    if not text_sections:
        return ""

    # Skip spreadsheet sources (they contain table data, not useful for summary)
    spreadsheet_extensions = (".xlsx", ".xls", ".csv")
    filtered_sections = [
        s for s in text_sections
        if not s.get("source", "").lower().endswith(spreadsheet_extensions)
    ]

    if not filtered_sections:
        return ""

    parts: list[str] = ["## SOURCE DOCUMENTS (SUMMARY)\n"]

    by_source: dict[str, list[str]] = {}
    for section in filtered_sections:
        src = section.get("source", "unknown")
        by_source.setdefault(src, []).append(section.get("content", ""))

    for src, contents in by_source.items():
        parts.append(f"### {src}\n")
        parts.extend(contents[:_SUMMARY_MAX_SECTIONS_PER_SOURCE])
        if len(contents) > _SUMMARY_MAX_SECTIONS_PER_SOURCE:
            parts.append(f"\n[... {len(contents) - _SUMMARY_MAX_SECTIONS_PER_SOURCE} more sections omitted ...]")
        parts.append("")

    return "\n".join(parts)


def _build_full_text_document_context(text_sections: list[dict]) -> str:
    """Build a full document context excluding spreadsheet sources.

    Includes all text sections from non-spreadsheet sources (PDF/DOCX/etc.)
    without truncation. This keeps text context available for FULL slides
    while avoiding large spreadsheet tables.
    """
    if not text_sections:
        return ""

    spreadsheet_extensions = (".xlsx", ".xls", ".csv")
    filtered_sections = [
        s for s in text_sections
        if not s.get("source", "").lower().endswith(spreadsheet_extensions)
    ]

    if not filtered_sections:
        return ""

    parts: list[str] = ["## SOURCE DOCUMENTS (TEXT)\n"]

    by_source: dict[str, list[str]] = {}
    for section in filtered_sections:
        src = section.get("source", "unknown")
        by_source.setdefault(src, []).append(section.get("content", ""))

    for src, contents in by_source.items():
        parts.append(f"### {src}\n")
        parts.extend(contents)
        parts.append("")

    return "\n".join(parts)

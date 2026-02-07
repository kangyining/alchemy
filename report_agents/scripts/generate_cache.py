#!/usr/bin/env python3
"""Generate Document AI cache for testing.

This script parses test documents using Document AI and caches the results
to avoid repeated API calls during development and testing.

Usage:
    python -m report_agents.scripts.generate_cache [--input-dir PATH] [--output PATH]

Examples:
    # Using default paths (./test_documents/ -> .cache/ingestion_cache.pkl)
    python -m report_agents.scripts.generate_cache

    # Custom input directory
    python -m report_agents.scripts.generate_cache --input-dir ./my_test_docs/

    # Custom output path
    python -m report_agents.scripts.generate_cache --output ./custom_cache.pkl
"""

import argparse
import asyncio
import logging
import os
import pickle
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from report_agents.tools.document_parser import parse_documents, _get_mime_type

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Default paths
DEFAULT_INPUT_DIR = Path(__file__).parent.parent.parent / "test_documents"
DEFAULT_OUTPUT_PATH = Path(__file__).parent.parent.parent / ".cache" / "ingestion_cache.pkl"


def collect_files_from_directory(input_dir: Path) -> list[tuple[str, bytes, str]]:
    """Collect all parseable files from a directory.

    Args:
        input_dir: Directory containing test documents

    Returns:
        List of (filename, bytes, mime_type) tuples
    """
    files = []

    # Supported extensions
    extensions = {".pdf", ".xlsx", ".xls", ".csv", ".docx", ".pptx"}

    for file_path in input_dir.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in extensions:
            logger.info(f"Found file: {file_path.name}")
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            mime_type = _get_mime_type(file_path.name)
            files.append((file_path.name, file_bytes, mime_type))

    return files


async def generate_cache(input_dir: Path, output_path: Path) -> None:
    """Generate cache from test documents.

    Args:
        input_dir: Directory containing test documents
        output_path: Path to save cache file
    """
    # Collect files
    logger.info(f"Collecting files from: {input_dir}")
    files = collect_files_from_directory(input_dir)

    if not files:
        logger.error(f"No parseable files found in {input_dir}")
        logger.info("Supported formats: PDF, XLSX, XLS, CSV, DOCX, PPTX")
        sys.exit(1)

    logger.info(f"Found {len(files)} file(s): {[f[0] for f in files]}")

    # Parse documents using Document AI
    logger.info("Parsing documents with Document AI...")
    result = await parse_documents(files)

    if result.get("status") == "error":
        logger.error(f"Parsing failed: {result.get('errors')}")
        sys.exit(1)

    logger.info(f"Parsing complete:")
    logger.info(f"  - Documents parsed: {result.get('documents_parsed', 0)}")
    logger.info(f"  - Text sections: {result.get('text_sections', 0)}")
    logger.info(f"  - Tables found: {result.get('tables_found', 0)}")

    # Prepare cache data
    cache_data = {
        "state_delta": {
            "full_text_document_context": result.get("full_text_document_context", ""),
            "summary_document_context": result.get("summary_document_context", ""),
            "full_document_context": result.get("full_document_context", ""),
            "parsed_tables_json": result.get("parsed_tables_json", "[]"),
        },
        "dataframes": result.get("dataframes", {}),
        "metadata": {
            "files_parsed": [f[0] for f in files],
            "documents_parsed": result.get("documents_parsed", 0),
            "text_sections": result.get("text_sections", 0),
            "tables_found": result.get("tables_found", 0),
        }
    }

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save cache
    with open(output_path, "wb") as f:
        pickle.dump(cache_data, f)

    cache_size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"Cache saved to: {output_path} ({cache_size_mb:.2f} MB)")

    # Show text context sizes
    full_text_len = len(cache_data["state_delta"]["full_text_document_context"])
    summary_len = len(cache_data["state_delta"]["summary_document_context"])
    logger.info(f"Context sizes:")
    logger.info(f"  - Full text context: {full_text_len:,} chars")
    logger.info(f"  - Summary context: {summary_len:,} chars")
    logger.info(f"  - DataFrames cached: {len(cache_data['dataframes'])}")

    logger.info("\nTo use cached ingestion, set: USE_CACHED_INGESTION=true")


def main():
    parser = argparse.ArgumentParser(
        description="Generate Document AI cache for testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Directory containing test documents (default: {DEFAULT_INPUT_DIR})"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Output cache file path (default: {DEFAULT_OUTPUT_PATH})"
    )

    args = parser.parse_args()

    # Validate input directory
    if not args.input_dir.exists():
        logger.error(f"Input directory does not exist: {args.input_dir}")
        logger.info(f"\nTo create it, run:")
        logger.info(f"  mkdir -p {args.input_dir}")
        logger.info(f"\nThen place your test documents (PDF, XLSX, etc.) in that directory.")
        sys.exit(1)

    if not args.input_dir.is_dir():
        logger.error(f"Input path is not a directory: {args.input_dir}")
        sys.exit(1)

    # Run cache generation
    asyncio.run(generate_cache(args.input_dir, args.output))


if __name__ == "__main__":
    main()

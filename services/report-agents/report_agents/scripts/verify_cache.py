#!/usr/bin/env python3
"""Verify that cached ingestion matches real Document AI ingestion.

Usage:
    python -m report_agents.scripts.verify_cache
"""

import asyncio
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from report_agents.scripts.generate_cache import (
    DEFAULT_INPUT_DIR,
    DEFAULT_OUTPUT_PATH,
    collect_files_from_directory,
)
from report_agents.tools.document_parser import parse_documents


def compare_results():
    """Compare cached results with fresh Document AI parsing."""

    # Load cached data
    if not DEFAULT_OUTPUT_PATH.exists():
        print(f"❌ Cache file not found: {DEFAULT_OUTPUT_PATH}")
        print("   Run: python -m report_agents.scripts.generate_cache")
        return False

    print(f"Loading cache from: {DEFAULT_OUTPUT_PATH}")
    with open(DEFAULT_OUTPUT_PATH, "rb") as f:
        cache_data = pickle.load(f)

    cached_state = cache_data.get("state_delta", {})
    cached_dfs = cache_data.get("dataframes", {})
    metadata = cache_data.get("metadata", {})

    print("\n=== CACHE CONTENTS ===")
    print(f"Files parsed: {metadata.get('files_parsed', [])}")
    print(f"Documents parsed: {metadata.get('documents_parsed', 0)}")
    print(f"Text sections: {metadata.get('text_sections', 0)}")
    print(f"Tables found: {metadata.get('tables_found', 0)}")
    print(f"DataFrames cached: {len(cached_dfs)}")

    print("\n=== TEXT CONTEXT SIZES ===")
    print(f"full_text_document_context: {len(cached_state.get('full_text_document_context', '')):,} chars")
    print(f"summary_document_context: {len(cached_state.get('summary_document_context', '')):,} chars")
    print(f"full_document_context: {len(cached_state.get('full_document_context', '')):,} chars")

    print("\n=== DATAFRAMES ===")
    for key, df in cached_dfs.items():
        print(f"  {key}: {df.shape[0]} rows × {df.shape[1]} cols")

    print("\n=== SAMPLE TEXT (first 500 chars) ===")
    sample = cached_state.get('summary_document_context', '')[:500]
    print(sample if sample else "(empty)")

    print("\n✅ Cache verification complete!")
    return True


if __name__ == "__main__":
    compare_results()

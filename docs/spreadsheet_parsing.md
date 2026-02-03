# Spreadsheet Parsing Logic

This document describes how Excel (`.xlsx`, `.xls`) and CSV files are parsed in the document parser.

## Overview

Spreadsheets are parsed **natively using pandas** rather than through Document AI. This approach:
- Eliminates Document AI API costs for spreadsheet files
- Provides full sheet support (Document AI has page limits)
- Gives precise control over data formatting

## Token Optimization Strategies

The parser applies several optimizations to reduce token count when sending data to LLMs:

| Optimization | Before | After | Savings |
|--------------|--------|-------|---------|
| NaN → empty | `value,nan,nan,value` | `value,,,value` | ~3 chars/cell |
| Round floats | `395349.3911902728` | `395349.39` | ~8 chars/value |
| Clean headers | `Unnamed: 0,Unnamed: 1` | `,` | ~10 chars/column |
| CSV format | `[["a","b"],["c","d"]]` | `a,b\nc,d` | ~57% reduction |
| Filter empty rows | Rows with all NaN/empty | Removed | Variable |

## Processing Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  Input: (filename, bytes, mime_type)                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. Load with pandas                                            │
│     - CSV: pd.read_csv()                                        │
│     - Excel: pd.read_excel(sheet_name=None) → all sheets        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. For each sheet:                                             │
│     a. Truncate to MAX_ROWS_PER_SHEET (2000)                    │
│     b. Apply optimizations:                                     │
│        - Round float columns to 2 decimal places                │
│        - Fill NaN with empty string                             │
│        - Replace "Unnamed:*" headers with empty string          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. Generate two outputs per sheet:                             │
│                                                                 │
│     TEXT SECTION (for markdown context):                        │
│     - df.to_markdown() with optimizations applied               │
│     - Used in full_document_context                             │
│                                                                 │
│     STRUCTURED TABLE (for programmatic access):                 │
│     - headers: list of column names                             │
│     - rows_csv: compact CSV string                              │
│     - row_count: number of non-empty rows                       │
└─────────────────────────────────────────────────────────────────┘
```

## CSV Cell Escaping

The `_rows_to_csv()` function properly escapes cells that contain:
- Commas (`,`)
- Double quotes (`"`)
- Newlines (`\n`)

Escaping follows standard CSV rules:
```python
# Cell with comma: wrap in quotes
"value with, comma" → "\"value with, comma\""

# Cell with quote: double the quote, wrap in quotes
'say "hello"' → "\"say \"\"hello\"\"\""
```

## Output Structure

### Text Section
```python
{
    "source": "financials.xlsx",
    "content": "#### Sheet: Q1 Results\n\n| Revenue | Cost | Profit |\n|---|---|---|\n| 1000.00 | 600.00 | 400.00 |"
}
```

### Structured Table
```python
{
    "source": "financials.xlsx",
    "sheet": "Q1 Results",
    "headers": ["Revenue", "Cost", "Profit"],
    "rows_csv": "Revenue,Cost,Profit\n1000.00,600.00,400.00",
    "row_count": 1
}
```

## Configuration

| Constant | Default | Description |
|----------|---------|-------------|
| `_MAX_ROWS_PER_SHEET` | 2000 | Max rows included per sheet |
| `_SPREADSHEET_MIME_TYPES` | xlsx, xls, csv | MIME types parsed natively |

## File Location

Implementation: `report_agents/tools/document_parser.py`

Key functions:
- `_parse_spreadsheet()` - Main entry point for spreadsheet parsing
- `_rows_to_csv()` - Converts rows to compact CSV format
- `_escape_csv_cell()` - Handles CSV escaping
- `_is_empty_row()` - Filters out empty/NaN rows

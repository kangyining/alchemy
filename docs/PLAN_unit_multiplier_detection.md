# Plan: Detect and Surface Unit Multipliers from Financial Spreadsheets

## Context
Financial Excel files commonly express dollar values with a unit qualifier in headers (e.g., "($ in thousands)"). When pandas reads these files, it stores raw numbers (e.g., 22,600) without the unit context. The SQL extraction and chart generation then treats 22,600 as the literal value, displaying it as "22.6M" when it should be "$22.6 billion" (22,600 × 1,000). This causes incorrect charts and reports.

## Approach: Detect → Store → Surface (3 layers)
Rather than scaling numeric values at ingestion (risky — would also scale year columns, counts, percentages), we detect unit metadata and surface it to the LLM so it can apply multipliers intelligently in SQL queries.

---

## Changes

### 1. `report_agents/tools/document_parser.py` — Detect unit multipliers (per sheet)

Add a `_detect_unit_multiplier(sheet_name, df)` function that scans **per sheet** (not per file — each sheet can have different units):
- **Sheet name string** (e.g., "Income Statement ($ in thousands)")
- **First 10 rows** of the raw DataFrame (before sanitization) — financial spreadsheets often have a header row like "Amounts in thousands" before the data starts. 10 rows covers virtually all financial layouts.
- **Column headers** (e.g., "Revenue ($M)")

Regex patterns for common financial conventions:
```python
UNIT_PATTERNS = [
    (re.compile(r'in thousands|[\(\s]\$?000s?[\)\s\']', re.I), 1_000,     "thousands"),
    (re.compile(r'in millions|[\(\s]\$?MM?[\)\s]', re.I),      1_000_000, "millions"),
    (re.compile(r'in billions|[\(\s]\$?BN?[\)\s]', re.I),       1_000_000_000, "billions"),
]
```

Returns: `{"multiplier": int, "unit_label": str, "note": str}` or `{"multiplier": 1, "unit_label": "", "note": ""}` if none detected.

Update `_parse_spreadsheet()` to:
- Call `_detect_unit_multiplier(sheet_name, df)` for each sheet independently
- Return a parallel `unit_notes` dict alongside `dataframes` (keyed by same `source:sheet` key)

### 2. `report_agents/services/database_service.py` — Store and surface metadata

**Schema change** — add `unit_note` column to `table_metadata`:
```sql
unit_note TEXT DEFAULT ''
```

**`store_dataframe()`** — accept optional `unit_note` parameter and store it.

**`get_schema_context()`** — when `unit_note` is non-empty, add a prominent warning line:
```
⚠️ UNIT NOTE: Dollar values in this table are expressed in thousands.
   Multiply numeric dollar amounts by 1,000 to get actual values.
```

### 3. `report_agents/tools/data_query.py` — Make SQL generation unit-aware

Add rule to `SQL_GENERATION_PROMPT`:
```
8. IMPORTANT: Check for UNIT NOTE warnings in the schema. If values are expressed
   in thousands/millions/billions, apply the appropriate multiplier in your SELECT
   (e.g., column_name * 1000) so results reflect actual dollar amounts.
```

### 4. `report_agents/sub_agents/ingestion_agent.py` — Pass unit metadata through

Update the `store_dataframe()` call to pass through the `unit_note` detected during parsing.

---

## Files to Modify
1. `report_agents/tools/document_parser.py` — add `_detect_unit_multiplier()`, update `_parse_spreadsheet()` return
2. `report_agents/services/database_service.py` — add `unit_note` to schema, `store_dataframe()`, `get_schema_context()`
3. `report_agents/tools/data_query.py` — update `SQL_GENERATION_PROMPT`
4. `report_agents/sub_agents/ingestion_agent.py` — pass `unit_note` to `store_dataframe()`

## Verification
1. Check that `_detect_unit_multiplier()` correctly detects patterns from a test spreadsheet with "($ in thousands)" header
2. Check that `get_schema_context()` includes the unit warning in its output
3. Run the full pipeline with the blackstone.xlsx file and verify the chart shows correct values (billions, not millions)

# Plan: Store Excel/CSV Data in SQLite with Natural Language Queries

## Problem
Large Excel files (19 tabs) consume ~260k tokens because the entire document context is passed to every slide agent, even when they only need specific metrics.

## Solution Overview
Store parsed tabular data in a **SQLite database** (session-scoped) and create a `query_financial_data` tool that allows agents to fetch only the data they need via natural language queries.

**Expected token reduction: 97.5%** (from ~260k to ~2k per data-dependent slide)

---

## Architecture

```
Document Upload
       ↓
IngestionAgent (Modified)
  1. Parse Excel/CSV → pandas DataFrames (unchanged)
  2. Store DataFrames in SQLite database (NEW)
  3. Emit schema metadata to state (instead of full context)
       ↓
SQLite Database: /tmp/report_agents/{session_id}.db
  - table_metadata: source_file, sheet_name, column info
  - {dynamic_tables}: one per sheet with actual data
       ↓
Slide Agents (Modified)
  - Receive schema metadata (not full data)
  - Use query_financial_data tool → NL to SQL → targeted results
  - Generate slides with only the data they need
```

---

## Why SQLite (Not BigQuery)

| Factor | SQLite | BigQuery |
|--------|--------|----------|
| Query latency | ~1-10ms | 500ms-2s |
| Cost | Free | $5/TB scanned |
| Setup | Zero (Python stdlib) | GCP credentials needed |
| NL-to-SQL | Custom (LLM call) | Built-in `ask_data_insights` |
| Session isolation | Natural (file per session) | Requires partitioning |

SQLite wins for this use case: fast, free, simple, and financial reports are typically <100MB.

---

## Implementation Steps

### 1. Create Database Service
**New file:** `report_agents/services/database_service.py`

```python
class FinancialDataStore:
    def __init__(self, session_id: str)
    def store_dataframe(self, df: pd.DataFrame, source_file: str, sheet_name: str)
    def execute_query(self, sql: str) -> list[dict]
    def get_schema_context(self) -> str  # For LLM context
```

Schema:
- `table_metadata`: tracks source files, sheet names, column info
- Dynamic tables: one per sheet (e.g., `financials_xlsx_income_statement`)

### 2. Create Query Tool
**New file:** `report_agents/tools/data_query.py`

```python
def query_financial_data(query: str, tool_context: ToolContext) -> dict:
    """Query financial data using natural language.

    Examples:
    - "Get total revenue for Q4 2023"
    - "Show all expense categories and amounts"
    - "Find gross profit margin for each quarter"
    """
```

**NL-to-SQL approach:** Use `gemini-2.0-flash` to convert natural language to SQL (~150 tokens per query vs 260k for full context).

### 3. Modify document_parser.py
**File:** `report_agents/tools/document_parser.py`

- Return raw DataFrames alongside existing CSV output
- Backward compatible: existing code continues to work

```python
def _parse_spreadsheet(...) -> tuple[list[dict], list[dict], dict[str, pd.DataFrame]]:
    # ... existing logic ...
    dataframes[sheet_name] = df_optimized.copy()  # NEW
    return text_sections, tables, dataframes
```

### 4. Modify IngestionAgent
**File:** `report_agents/sub_agents/ingestion_agent.py`

- Store DataFrames in SQLite after parsing
- Emit `db_path` and `table_schemas` to state (instead of `full_document_context`)

### 5. Modify Callbacks
**File:** `report_agents/utils/callbacks.py`

- For FULL context slides: inject schema metadata + instruct to use query tool
- Keep SUMMARY context unchanged for TEXT slides (Cover, Outlook)

### 6. Update Slide Agent Factory
**File:** `report_agents/sub_agents/slide_agent_factory.py`

- Add `query_financial_data` tool to TABLE/CHART/MIXED slides
- Update prompts to instruct agents to query for specific data

---

## Files to Modify

| File | Change |
|------|--------|
| `report_agents/services/database_service.py` | NEW - SQLite storage class |
| `report_agents/tools/data_query.py` | NEW - NL query tool |
| `report_agents/tools/document_parser.py` | Return raw DataFrames |
| `report_agents/sub_agents/ingestion_agent.py` | Store to SQLite, emit schema |
| `report_agents/utils/callbacks.py` | Inject schema instead of full context |
| `report_agents/sub_agents/slide_agent_factory.py` | Add query tool to agents |
| `report_agents/prompts/*.py` | Update prompts to use query tool |

---

## Token Usage Comparison

| Slide Type | Before | After | Reduction |
|------------|--------|-------|-----------|
| Cover (TEXT) | ~10k | ~10k | 0% |
| Financial Highlights (TABLE) | ~260k | ~2k | 99% |
| Revenue Breakdown (CHART) | ~260k | ~1.5k | 99% |
| Balance Sheet (TABLE) | ~260k | ~2k | 99% |
| Cash Flow (MIXED) | ~260k | ~2.5k | 99% |
| **Total per report** | ~1.85M | ~45k | **97.5%** |

---

## Migration Strategy (Clean Switch)

1. Implement all changes in one go
2. Replace `full_document_context` injection with SQLite queries
3. Keep `summary_document_context` for TEXT slides (Cover, Outlook)
4. Add database cleanup on session end

---

## Verification

1. Run existing test suite to ensure backward compatibility
2. Test with 19-tab Excel file:
   - Verify all sheets stored in SQLite
   - Test NL queries for common financial metrics
3. Compare slide output quality (before vs after)
4. Measure actual token usage reduction
5. Test session cleanup (database file deletion)

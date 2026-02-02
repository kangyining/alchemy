# Plan: Add Extraction Agent to Report Pipeline

## Goal
Insert an LLM-based ExtractionAgent between IngestionAgent and slide generation. It reads the full document context once, extracts structured JSON data for all 10 slides, and stores per-slide data in session state. Slide agents then receive only their small, focused JSON payload instead of the entire document.

## Key Design Decisions
- **One LLM call, per-slide state keys**: Extraction agent outputs one JSON object, then a deterministic splitter fans it out to `slide_NN_extracted_data` state keys (with shared `common` fields merged into each).
- **All 10 slides use extracted data**: Eliminates the `summary_document_context` vs `full_document_context` split. One uniform callback for all slides.
- **No fallback to full context**: If extraction misses a field, slide agents report `[NOT FOUND IN SOURCE]` rather than re-scanning the full document.
- **Keep sequential execution for now**: Reduce throttle delay from 10s to 2s. Parallel slide execution is a follow-up optimization.
- **Slide agents keep their tools**: `calculate_financial_metrics` and chart generation tools stay on slide agents. The extraction agent only extracts raw data points.

---

## Implementation Steps

### Step 1: Define extraction schema
**New file:** `report_agents/utils/extraction_schema.py`

Define a Python dict (or docstring) specifying the JSON schema the extraction agent must produce. Structure:
```json
{
  "common": { "company_name": "", "reporting_period": "", "report_date": "", "source_filenames": [] },
  "slide_01": { "report_title": "" },
  "slide_02": {
    "total_revenue": {"value": null, "unit": "", "source": ""},
    "prior_revenue": {"value": null, "unit": "", "source": ""},
    "net_income": {"value": null, "unit": "", "source": ""},
    "ebitda": {"value": null, "unit": "", "source": ""},
    "key_highlights": []
  },
  "slide_03": {
    "metrics": [{"name": "", "current_value": null, "prior_value": null, "unit": "", "source": ""}]
  },
  "slide_04": { "segments": [{"name": "", "value": null}], "period_label": "" },
  "slide_05": { "expenses": [{"category": "", "amount": null}] },
  "slide_06": { "periods": [{"period": "", "metric_name": "", "value": null}] },
  "slide_07": {
    "items": [{"name": "", "current_value": null, "prior_value": null}]
  },
  "slide_08": {
    "operating_cf": null, "investing_cf": null, "financing_cf": null,
    "capex": null, "dividends": null
  },
  "slide_09": {
    "ratios": [{"name": "", "current_value": null, "prior_value": null}]
  },
  "slide_10": {
    "management_guidance": [], "key_risks": [], "strategic_initiatives": []
  }
}
```
Each numeric field is `{value: float|null, unit: str, source: str}`.

### Step 2: Create extraction prompt
**New file:** `report_agents/prompts/extraction_prompt.py`

Single prompt instructing the LLM to:
- Read full document content + parsed tables
- Output valid JSON matching the schema from Step 1
- Use `null` for any field not found
- Include `_sources` list per slide section
- Never guess or fabricate numbers

### Step 3: Add new state keys
**Modify:** `report_agents/utils/state_keys.py`

Add:
- `RAW_EXTRACTED_JSON = "raw_extracted_json"`
- `EXTRACTION_STATUS = "extraction_status"`
- `slide_extracted_data_key(n)` helper function

### Step 4: Create extraction agent
**New file:** `report_agents/sub_agents/extraction_agent.py`

Two-part agent wrapped in a `SequentialAgent`:
1. **ExtractionLlmAgent** (`LlmAgent`): Uses `prepare_full_context_request` callback (existing), outputs to `raw_extracted_json` state key. Model: same as other agents.
2. **ExtractionSplitterAgent** (`BaseAgent`): Deterministic. Parses JSON, merges `common` fields into each slide's data, writes `slide_01_extracted_data` through `slide_10_extracted_data` to state. Includes try/except for malformed JSON.

### Step 5: Add new callback for extracted data injection
**Modify:** `report_agents/utils/callbacks.py`

Add `prepare_extracted_context_request`:
- Parses slide number from agent name (`SlideAgent_NN_*` pattern)
- Reads `slide_NN_extracted_data` from state
- Injects as a JSON code block in a system/user message at position 0
- Strips uploaded file parts (reuses existing `strip_file_parts`)

### Step 6: Update slide agent factory
**Modify:** `report_agents/sub_agents/slide_agent_factory.py`

- Replace `prepare_full_context_request` / `prepare_summary_context_request` with `prepare_extracted_context_request` for ALL slides
- Remove the `if spec.slide_number not in (1, 2): continue` filter
- Reduce `INTER_SLIDE_DELAY_SECONDS` from 10 to 2

### Step 7: Update slide prompts
**Modify:** All 10 `report_agents/prompts/slide_*.py` files

Shift wording from "extract from the document above" to "use the structured JSON data provided above." Prompts become shorter and focused on formatting + tool usage rather than data extraction.

**Modify:** `report_agents/prompts/registry.py`

Update `ACCURACY_SUFFIX` to reference extracted JSON data instead of raw source documents.

### Step 8: Update root orchestrator
**Modify:** `report_agents/agent.py`

Insert `extraction_agent` into the pipeline:
```
SequentialAgent: [ingestion_agent, extraction_agent, sequential_slide_generation, assembly_agent]
```

### Step 9: Update session initializer
**Modify:** `report_agents/tools/initializer.py`

Add default empty values for `raw_extracted_json`, `extraction_status`, and all 10 `slide_NN_extracted_data` keys.

---

## Files Changed Summary

| File | Action |
|------|--------|
| `report_agents/utils/extraction_schema.py` | NEW |
| `report_agents/prompts/extraction_prompt.py` | NEW |
| `report_agents/sub_agents/extraction_agent.py` | NEW |
| `report_agents/utils/state_keys.py` | MODIFY |
| `report_agents/utils/callbacks.py` | MODIFY |
| `report_agents/sub_agents/slide_agent_factory.py` | MODIFY |
| `report_agents/prompts/slide_01_cover.py` | MODIFY |
| `report_agents/prompts/slide_02_executive_summary.py` | MODIFY |
| `report_agents/prompts/slide_03_financial_highlights.py` | MODIFY |
| `report_agents/prompts/slide_04_revenue_breakdown.py` | MODIFY |
| `report_agents/prompts/slide_05_expense_analysis.py` | MODIFY |
| `report_agents/prompts/slide_06_profitability.py` | MODIFY |
| `report_agents/prompts/slide_07_balance_sheet.py` | MODIFY |
| `report_agents/prompts/slide_08_cash_flow.py` | MODIFY |
| `report_agents/prompts/slide_09_key_ratios.py` | MODIFY |
| `report_agents/prompts/slide_10_outlook.py` | MODIFY |
| `report_agents/prompts/registry.py` | MODIFY |
| `report_agents/agent.py` | MODIFY |
| `report_agents/tools/initializer.py` | MODIFY |

---

## Token & TPM Analysis

### Current Architecture (all 10 slides enabled)

| Component | Input tokens/call | Calls | Total input tokens |
|---|---|---|---|
| Slides 1, 2, 10 (summary context) | ~5,000 | 3 | ~15,000 |
| Slides 3-9 (full context) | ~25,000 | 7 | **~175,000** |
| **Total** | | **10** | **~190,000** |

### With Extraction Agent

| Component | Input tokens/call | Calls | Total input tokens |
|---|---|---|---|
| Extraction agent (full context) | ~25,000 | 1 | ~25,000 |
| Each slide agent (small JSON) | ~1,000-2,000 | 10 | ~10,000-20,000 |
| **Total** | | **11** | **~35,000-45,000** |

### Result: ~75-80% reduction in total input tokens

### TPM Impact
- **Current**: 7 slide agents x ~25k tokens in ~70s (with 10s throttle) = ~175k tokens/min → blows past typical 100-200k TPM limits
- **After**: 1 extraction call (~25k) + 10 small slide calls (~15k total) = ~40k tokens/min → comfortably within TPM limits
- Throttle delays can be reduced from 10s to ~2s or removed entirely
- **Caveat**: For very large documents (100k+ tokens), even the single extraction call may approach TPM limits

---

## Verification
1. Run the full pipeline with a sample financial document end-to-end
2. Verify extraction JSON contains all expected fields with correct values
3. Verify each slide output references correct numbers from extracted data
4. Compare token usage before/after (expect significant reduction on slide agents)
5. Confirm `[NOT FOUND IN SOURCE]` appears for genuinely missing data rather than hallucinated numbers

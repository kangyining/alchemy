# Document AI Cache Scripts

These scripts help reduce Document AI costs during development by caching parsed document results.

## Quick Start

```bash
# 1. Put test documents in the test_documents folder
cp your-docs/*.pdf ../../test_documents/
cp your-docs/*.xlsx ../../test_documents/

# 2. Generate cache (one-time Document AI cost)
python -m report_agents.scripts.generate_cache

# 3. Enable cached mode in report_agents/agent.py
#    Set: USE_CACHED_INGESTION = True

# 4. Run ADK as usual
adk web
```

## Scripts

### generate_cache.py

Parses documents using Document AI and saves results to `.cache/ingestion_cache.pkl`.

```bash
# Default: reads from test_documents/, writes to .cache/
python -m report_agents.scripts.generate_cache

# Custom paths
python -m report_agents.scripts.generate_cache --input-dir ./my_docs/ --output ./my_cache.pkl
```

**Supported file types:** PDF, XLSX, XLS, CSV, DOCX, PPTX

### verify_cache.py

Inspects the cache contents to verify what was parsed.

```bash
python -m report_agents.scripts.verify_cache
```

## How It Works

1. **generate_cache.py** calls Document AI once and saves:
   - Parsed text contexts (full + summary)
   - DataFrames from spreadsheets (as pandas objects)

2. **CachedIngestionAgent** loads the cache and:
   - Restores text contexts directly
   - Recreates SQLite database from cached DataFrames (free, no API calls)

## Switching Modes

In `report_agents/agent.py`:

```python
# For testing (no Document AI calls)
USE_CACHED_INGESTION = True

# For production (real Document AI)
USE_CACHED_INGESTION = False
```

## Cost Savings

| Operation | Real Mode | Cached Mode |
|-----------|-----------|-------------|
| Document AI parsing | $$$ per page | FREE |
| Spreadsheet parsing | FREE | FREE |
| SQLite operations | FREE | FREE |

## File Locations

| Path | Description |
|------|-------------|
| `test_documents/` | Put your test docs here |
| `.cache/ingestion_cache.pkl` | Generated cache file |
| `report_agents/agent.py` | Toggle `USE_CACHED_INGESTION` |

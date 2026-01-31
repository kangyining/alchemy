# Financial Report Generation System — Implementation Plan

## Overview

Build a multi-agent financial report generator using **Google ADK** (Agent Development Kit). Users upload documents (Word, Excel, CSV, PDF), and a pipeline of agents extracts information per-slide, generates charts programmatically, and outputs PPTX + PDF files. Start with ADK Web UI; later wrap with FastAPI for React frontend.

---

## Architecture

```
User uploads docs (ADK Web UI)
         │
         ▼
┌─────────────────────────────────┐
│  SequentialAgent (root_agent)   │
│                                 │
│  1. IngestionAgent              │  ← Parses all docs into session state
│     └─ tool: parse_documents()  │     (deterministic, no LLM parsing)
│                                 │
│  2. ParallelAgent               │  ← All slide agents run concurrently
│     ├─ SlideAgent_01 (text)     │     Each reads state, writes to unique key
│     ├─ SlideAgent_02 (text)     │     Chart agents call chart tools
│     ├─ SlideAgent_05 (chart)────┼──── tool: generate_bar_chart()
│     ├─ ...                      │
│     └─ SlideAgent_N             │
│                                 │
│  3. AssemblyAgent               │  ← Builds PPTX + PDF from all slide outputs
│     └─ tool: assemble_report()  │     Saves as ADK artifacts for download
└─────────────────────────────────┘
```

### Data Flow Through Session State

| Phase | Reads | Writes |
|-------|-------|--------|
| Ingestion | artifacts (uploaded files) | `state["parsed_documents"]`, `state["parsed_tables_json"]` |
| Slide agents | `state["parsed_documents"]`, `state["parsed_tables_json"]` | `state["slide_01_content"]`, `state["slide_05_chart_image"]`, etc. |
| Assembly | all `state["slide_*"]` keys + chart artifacts | artifacts: `financial_report.pptx`, `financial_report.pdf` |

No race conditions — each slide agent writes to its own unique key.

---

## Project Structure

```
report-agents/
├── pyproject.toml
├── .env                              # GOOGLE_API_KEY
├── report_agents/                    # ADK agent package (discovered by `adk web`)
│   ├── __init__.py
│   ├── agent.py                      # root_agent — SequentialAgent orchestrator
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── registry.py               # SlideSpec registry: slide_number, title, type, chart_type, prompt
│   │   ├── slide_01_cover.py         # Prompt constants per slide
│   │   ├── slide_02_executive_summary.py
│   │   └── ...
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── document_parser.py        # Parse PDF/Excel/CSV/DOCX → session state
│   │   ├── chart_generator.py        # matplotlib chart tools (bar, line, pie, etc.)
│   │   ├── financial_calc.py         # Deterministic financial calculations (YoY, margins)
│   │   └── report_builder.py         # Assemble PPTX + PDF from slide outputs
│   ├── sub_agents/
│   │   ├── __init__.py
│   │   ├── ingestion_agent.py        # LlmAgent wrapping document_parser tool
│   │   └── slide_agent_factory.py    # Creates N LlmAgents from registry
│   └── utils/
│       ├── __init__.py
│       ├── state_keys.py             # Constants: slide_content_key(n), slide_chart_image_key(n)
│       └── pptx_styles.py            # Colors, fonts, slide layout helpers
├── tests/
│   ├── test_document_parser.py
│   ├── test_chart_generator.py
│   └── test_report_builder.py
└── sample_data/                      # Test documents
```

---

## Key Design Decisions

### 1. Document Parsing is Deterministic (No LLM)

Parse docs with Python libraries (pdfplumber, pandas, python-docx), store raw text + tables in session state. LLMs only reason over already-extracted content. This prevents hallucination at the extraction layer.

### 2. Charts are Programmatic (matplotlib)

Slide agents extract data as structured JSON, then call chart tool functions. Tools render with matplotlib, save PNG as ADK artifact. Deterministic, reproducible, and accurate for financial data.

### 3. Intermediate Format is Markdown

Each slide agent outputs markdown text. This makes it easy to:
- Render into PPTX text boxes (parse headers, bullets, bold)
- Convert to HTML → PDF via WeasyPrint
- Human-review intermediate outputs

### 4. Financial Accuracy Safeguards

- Every prompt requires **verbatim quoting** with source citations
- Missing data → `[NOT FOUND IN SOURCE]` (never guess)
- Deterministic `financial_calc.py` tool for all math (YoY growth, margins, ratios)
- LLM never computes numbers directly

### 5. Prompt Registry as Single Source of Truth

`prompts/registry.py` defines a `SlideSpec` dataclass per slide:

```python
@dataclass
class SlideSpec:
    slide_number: int
    title: str
    slide_type: SlideType    # TEXT | TABLE | CHART | MIXED
    chart_type: ChartType    # BAR | LINE | PIE | NONE
    prompt: str              # Full system instruction
```

The factory reads this registry to create agents dynamically. Adding/removing slides = editing the registry.

---

## Implementation Steps

### Step 1: Project Setup

- Create `pyproject.toml` with all dependencies
- Create `.env` with `GOOGLE_API_KEY`
- Create full directory structure with `__init__.py` files
- Verify `adk web` starts with a minimal hello-world agent

### Step 2: Document Parser Tool (`tools/document_parser.py`)

- Implement `parse_uploaded_documents(tool_context)` ADK tool function
- Uses pdfplumber for PDF, pandas for Excel/CSV, python-docx for Word
- Reads uploaded files from ADK artifacts system
- Writes parsed content to session state:
  - `state["parsed_documents"]` — text sections with source attribution
  - `state["parsed_tables_json"]` — serialized table data

```python
def parse_uploaded_documents(tool_context: ToolContext) -> dict:
    artifact_names = tool_context.list_artifacts()
    parsed = {"text_sections": [], "tables": []}
    for name in artifact_names:
        artifact = tool_context.load_artifact(name)
        file_bytes = artifact.inline_data.data
        if name.endswith('.pdf'):
            text, tables = _parse_pdf(file_bytes)
            ...
        elif name.endswith(('.xlsx', '.csv')):
            tables = _parse_spreadsheet(file_bytes, name)
            ...
        elif name.endswith('.docx'):
            text = _parse_docx(file_bytes)
            ...
    tool_context.state["parsed_documents"] = parsed
    tool_context.state["parsed_tables_json"] = _tables_to_json(parsed["tables"])
```

### Step 3: Chart Generator Tools (`tools/chart_generator.py`)

- Implement ADK tool functions: `generate_bar_chart()`, `generate_line_chart()`, `generate_pie_chart()`
- Accept structured JSON data + slide_number
- Render with matplotlib (non-interactive `Agg` backend), save PNG as ADK artifact
- Store image artifact filename in `state["slide_XX_chart_image"]`
- Shared style config (colors, fonts, DPI) for consistent branding

```python
def generate_bar_chart(data_json: str, slide_number: int, tool_context: ToolContext) -> dict:
    data = json.loads(data_json)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(data["categories"], data["values"], color='#2E86AB')
    ax.set_title(data["title"])
    # ... styling, value labels
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150)
    plt.close(fig)
    tool_context.save_artifact(f"slide_{slide_number:02d}_chart.png", ...)
    tool_context.state[f"slide_{slide_number:02d}_chart_image"] = filename
```

### Step 4: Financial Calculation Tool (`tools/financial_calc.py`)

- Implement `calculate_financial_metrics(metric_type, current_value, previous_value)`
- Deterministic math: YoY growth, margins, ratios
- Returns result + formula string for transparency (e.g., `"(500 - 400) / |400| * 100 = 25.0%"`)

### Step 5: Prompt Registry & Slide Prompts

- `prompts/registry.py` — define `SLIDE_REGISTRY: list[SlideSpec]` with all slides
- Create prompt files per slide (placeholders for user's pre-written prompts)
- Every prompt includes these mandatory accuracy instructions:

```
CRITICAL RULES:
1. Every number MUST appear verbatim in the source documents
2. If a number is not found, write [NOT FOUND IN SOURCE]
3. End with a Sources section citing filename and page for each figure
4. For calculations, use the calculate_financial_metrics tool
```

### Step 6: Slide Agent Factory (`sub_agents/slide_agent_factory.py`)

- `create_slide_agents()` → `list[LlmAgent]`
- Reads `SLIDE_REGISTRY`, creates one LlmAgent per slide
- Text slides: no extra tools
- Chart slides: gets chart generator + financial calc tools
- Each agent's `output_key=f"slide_{n:02d}_content"` writes to unique state key

```python
def create_slide_agents() -> list[LlmAgent]:
    agents = []
    for spec in SLIDE_REGISTRY:
        tools = []
        if spec.slide_type in (SlideType.CHART, SlideType.MIXED):
            tools.append(CHART_TOOLS[spec.chart_type.value])
            tools.append(calculate_financial_metrics)
        agent = LlmAgent(
            name=f"SlideAgent_{spec.slide_number:02d}",
            model="gemini-2.5-flash-preview-05-20",
            instruction=spec.prompt,
            tools=tools,
            output_key=f"slide_{spec.slide_number:02d}_content",
        )
        agents.append(agent)
    return agents
```

### Step 7: Ingestion Agent (`sub_agents/ingestion_agent.py`)

- LlmAgent with `parse_uploaded_documents` tool
- Minimal LLM role: calls the parsing tool and summarizes what was found
- `output_key="ingestion_summary"` for downstream reference

### Step 8: Report Builder Tool (`tools/report_builder.py`)

- `assemble_report(tool_context)` — entirely deterministic, no LLM
- Reads all `slide_*` state keys + chart image artifacts
- **PPTX**: python-pptx, 16:9 widescreen, from scratch
  - Title bar with brand colors per slide
  - Markdown → text box rendering (headers, bullets, bold)
  - Chart images embedded via `add_picture()`
- **PDF**: Markdown → HTML (with Jinja2 template) → WeasyPrint
- Saves both as ADK artifacts for user download

### Step 9: Root Orchestrator (`agent.py`)

```python
from google.adk.agents import SequentialAgent, ParallelAgent

root_agent = SequentialAgent(
    name="FinancialReportOrchestrator",
    sub_agents=[
        ingestion_agent,                    # Phase 1: Parse documents
        ParallelAgent(                      # Phase 2: Generate all slides concurrently
            name="ParallelSlideGeneration",
            sub_agents=create_slide_agents(),
        ),
        assembly_agent,                     # Phase 3: Build PPTX + PDF
    ],
)
```

### Step 10: End-to-End Testing

- Run `adk web`, upload sample financial documents
- Verify full pipeline: docs parsed → slides generated → charts rendered → PPTX/PDF downloadable
- Accuracy check: every number in output matches source documents verbatim

---

## Dependencies

```
google-adk>=1.0.0
pandas>=2.0
openpyxl>=3.1
python-docx>=1.0
pdfplumber>=0.10
matplotlib>=3.8
python-pptx>=0.6.23
weasyprint>=60
markdown>=3.5
Jinja2>=3.1
```

---

## Running

```bash
cd /Users/qiyuanbao/Documents/inf-capital/report-agents
pip install -e .
adk web --port 8000
# Open http://localhost:8000, select report_agents, upload docs, type "Generate report"
```

---

## Future: React Frontend

Wrap the ADK agent in a FastAPI endpoint:
- `POST /api/reports/generate` — upload files, start generation, return session_id
- `GET /api/reports/{id}/status` — poll progress
- `GET /api/reports/{id}/download/{format}` — download PPTX or PDF

---

## Verification Checklist

1. `adk web` starts without errors
2. Upload sample Excel + PDF via Web UI
3. Type "Generate financial report" — observe agent orchestration in logs
4. Download PPTX — verify correct slide count, text content, embedded charts
5. Download PDF — verify formatting and content matches PPTX
6. Spot-check: every number in output appears verbatim in source documents

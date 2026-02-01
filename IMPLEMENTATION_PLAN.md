# Financial Report Generation System — Implementation Plan

## Overview

Build a multi-agent financial report generator using **Google ADK** (Agent Development Kit). Users upload documents (Word, Excel, CSV, PDF), and a pipeline of agents extracts information per-slide, generates charts programmatically, and outputs PPTX + PDF files. Start with ADK Web UI; later wrap with FastAPI for React frontend.

**Document parsing** uses **Google Cloud Document AI Layout Parser** — OCR-grounded, outputs markdown natively, supports PDF/DOCX/XLSX/PPTX, and preserves table structure with minimal hallucination risk.

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
│     └─ tool: parse_documents()  │     (Document AI Layout Parser, OCR-grounded)
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
├── .env                              # GOOGLE_API_KEY, GOOGLE_CLOUD_PROJECT, DOCAI_PROCESSOR_ID
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
│   │   ├── document_parser.py        # Document AI Layout Parser → markdown + tables → session state
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

### 1. Document Parsing via Google Cloud Document AI Layout Parser

Uses the **Gemini Layout Parser** processor from Document AI — not raw Python libraries or direct LLM parsing. Key advantages:
- **OCR-grounded**: Reads what's actually on the page, preventing hallucination at the extraction layer
- **Native markdown output**: Aligns directly with our intermediate format, no conversion needed
- **Semantic chunking**: Built-in context-aware chunking preserves table headers and section hierarchy
- **Format coverage**: GA support for PDF, DOCX, XLSX, PPTX — all required input formats
- **Table fidelity**: Preserves merged cells, row/column spans, and header structure
- Cost: ~$0.10-0.20 per document (well within budget for financial reports)
- Requires: Google Cloud project with Document AI API enabled, a Layout Parser processor

LLMs (Gemini via slide agents) only reason over the already-parsed markdown content downstream.

### Context Strategy: Pass Full Corpus to Every Slide Agent

With **Gemini 3 Pro's 2M token context window**, 10 parsed financial documents (~500K tokens) fit comfortably at ~25% capacity. Each slide agent receives the full parsed corpus — no routing, filtering, or RAG needed.

- **Why**: Financial slides often need cross-references (e.g., revenue slide needs income statement + management discussion). Full context ensures nothing is missed.
- **Cost**: ~$9-10 per report for slide agent input tokens. Acceptable for financial reports.
- **Future optimization**: If volume grows, add topic-based routing (match chunk headings to slide topics) to reduce cost 5-10x without rearchitecting.

### 2. Charts: Gemini Image Gen First, matplotlib Fallback

**Primary**: Slide agents extract data as structured JSON, then call a chart tool that uses **Gemini 3 Pro Image** (`gemini-3-pro-image-preview`) to generate polished, presentation-ready chart images (up to 4K resolution).

**Validation**: After generation, a validation step checks that key numbers/labels in the chart match the source data. Gemini image gen has ~<10% text error rate — acceptable for most charts but not guaranteed.

**Fallback**: If validation fails (numbers don't match, chart is garbled), the tool automatically falls back to **matplotlib** to produce a deterministic, pixel-accurate chart.

```
Slide Agent extracts data JSON
         │
         ▼
┌─ Chart Tool ──────────────────────────┐
│  1. Call Gemini 3 Pro Image Gen       │
│  2. Validate: OCR the output image,   │
│     compare numbers to source data    │
│  3. If valid → save as artifact       │
│  4. If invalid → fallback matplotlib  │
│     → save as artifact                │
└───────────────────────────────────────┘
```

This gives presentation-quality visuals by default with a safety net for financial accuracy.

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
- Create `.env` with `GOOGLE_API_KEY`, `GOOGLE_CLOUD_PROJECT`, `DOCAI_PROCESSOR_ID`, `DOCAI_LOCATION`
- Set up Google Cloud project: enable Document AI API, create Layout Parser processor
- Create full directory structure with `__init__.py` files
- Verify `adk web` starts with a minimal hello-world agent

### Step 2: Document Parser Tool (`tools/document_parser.py`)

- Implement `parse_uploaded_documents(tool_context)` ADK tool function
- Uses **Google Cloud Document AI Layout Parser** for all document formats
- Reads uploaded files from ADK artifacts system
- Sends each file to Document AI Layout Parser processor
- Receives **markdown + structured chunks** back (native output format)
- Writes parsed content to session state:
  - `state["parsed_documents"]` — markdown text per document with source attribution
  - `state["parsed_tables_json"]` — extracted table data as structured JSON

```python
from google.cloud import documentai_v1 as documentai

def parse_uploaded_documents(tool_context: ToolContext) -> dict:
    """Parse all uploaded documents using Document AI Layout Parser."""
    client = documentai.DocumentProcessorServiceClient()
    processor_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{PROCESSOR_ID}"

    artifact_names = tool_context.list_artifacts()
    parsed = {"text_sections": [], "tables": []}

    for name in artifact_names:
        artifact = tool_context.load_artifact(name)
        file_bytes = artifact.inline_data.data
        mime_type = _get_mime_type(name)  # application/pdf, etc.

        # Send to Document AI Layout Parser
        request = documentai.ProcessRequest(
            name=processor_name,
            raw_document=documentai.RawDocument(content=file_bytes, mime_type=mime_type),
            process_options=documentai.ProcessOptions(
                layout_config=documentai.ProcessOptions.LayoutConfig(
                    chunking_config=documentai.ProcessOptions.LayoutConfig.ChunkingConfig(
                        chunk_size=1000,
                        include_ancestor_headings=True,  # preserves section context
                    )
                )
            ),
        )
        result = client.process_document(request=request)

        # Layout Parser returns markdown natively in chunked_document
        for chunk in result.document.chunked_document.chunks:
            parsed["text_sections"].append({
                "source": name,
                "content": chunk.content,          # already markdown
                "page_span": chunk.page_span,
            })

        # Extract tables separately for chart agents
        for page in result.document.pages:
            for table in page.tables:
                parsed["tables"].append(_extract_table(table, name))

    tool_context.state["parsed_documents"] = parsed
    tool_context.state["parsed_tables_json"] = json.dumps(parsed["tables"])
```

**Setup required**: Create a Layout Parser processor in Google Cloud Console → Document AI → Create Processor → "Layout Parser". Store the processor ID in `.env`.

### Step 3: Chart Generator Tools (`tools/chart_generator.py`)

- Implement ADK tool functions: `generate_bar_chart()`, `generate_line_chart()`, `generate_pie_chart()`
- Accept structured JSON data + slide_number + chart description
- **Primary path**: Call Gemini 3 Pro Image (`gemini-3-pro-image-preview`) with detailed prompt including exact data values, style instructions, and chart type
- **Validation**: Use Gemini to OCR/verify the generated image — compare rendered numbers against source data JSON
- **Fallback**: If validation fails, render with matplotlib (non-interactive `Agg` backend) for guaranteed accuracy
- Save result as ADK artifact, store filename in `state["slide_XX_chart_image"]`
- Shared style prompt template for consistent branding across Gemini-generated charts

```python
from google import genai
from google.genai import types as genai_types

CHART_STYLE_PROMPT = """Professional financial report chart. Clean design,
dark navy (#1A3C6E) headers, blue (#2E86AB) bars/lines, white background.
Sans-serif font. Clear axis labels. Value labels on each data point.
High resolution, presentation-ready. 16:9 aspect ratio."""

def generate_bar_chart(data_json: str, slide_number: int, tool_context: ToolContext) -> dict:
    data = json.loads(data_json)

    # Step 1: Try Gemini image generation
    prompt = f"""{CHART_STYLE_PROMPT}
    Create a bar chart with title: "{data['title']}"
    X-axis label: "{data['x_label']}", Y-axis label: "{data['y_label']}"
    Categories and exact values (render these numbers precisely):
    {chr(10).join(f'  - {c}: {v}' for c, v in zip(data['categories'], data['values']))}
    """
    try:
        client = genai.Client()
        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=prompt,
            config=genai_types.GenerateContentConfig(response_modalities=["Image"]),
        )
        image_bytes = _extract_image_bytes(response)

        # Step 2: Validate — ask Gemini to read back the numbers from the image
        if _validate_chart_numbers(client, image_bytes, data):
            _save_chart_artifact(tool_context, slide_number, image_bytes)
            return {"status": "success", "method": "gemini_image_gen"}
    except Exception:
        pass  # Fall through to matplotlib

    # Step 3: Fallback to matplotlib
    image_bytes = _render_matplotlib_bar_chart(data)
    _save_chart_artifact(tool_context, slide_number, image_bytes)
    return {"status": "success", "method": "matplotlib_fallback"}

def _validate_chart_numbers(client, image_bytes, source_data) -> bool:
    """Ask Gemini to read the chart image and verify numbers match source data."""
    response = client.models.generate_content(
        model="gemini-3-pro-preview",
        contents=[
            genai_types.Part.from_data(data=image_bytes, mime_type="image/png"),
            "Read all numeric values visible in this chart. Return them as JSON."
        ],
    )
    # Compare extracted numbers against source_data values
    # Return True if all key values match within tolerance
    ...
```

**Validation approach**: Use Gemini 3 Pro (text model) to OCR the generated chart image and extract numbers. Compare against the source `data_json`. If key values don't match within a small tolerance (e.g., rounding), fall back to matplotlib.

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
            model="gemini-2.5-pro",
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
google-cloud-documentai>=2.20
google-cloud-documentai-toolbox>=0.13
pandas>=2.0
openpyxl>=3.1
matplotlib>=3.8
python-pptx>=0.6.23
weasyprint>=60
markdown>=3.5
Jinja2>=3.1
```

> **Note**: `pdfplumber`, `python-docx` removed — Document AI Layout Parser handles all formats natively (PDF, DOCX, XLSX, PPTX).

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

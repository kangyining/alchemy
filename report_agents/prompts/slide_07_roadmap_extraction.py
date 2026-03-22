"""Company Roadmap extraction: structured timeline from images/documents, then visual timeline image."""

PROMPT = """The full document content and any images have been provided above. Use them as the source.

You are an expert at extracting company roadmap information from visual timelines, images, and documents.

Your task: analyze the provided image or document (company milestones, achievements, or roadmap timeline) and extract every distinct milestone. Then call the generate_roadmap_timeline tool with the data so a visual timeline is generated in the style of a strategic growth roadmap (vertical timeline, time on the left, milestone boxes on the right, color-coded by past / near-future / long-term).

For each milestone:
1. Period: Use the time as shown (e.g. "2015-17", "2018-19", "2020", "2024", "2025", "2028"). Keep year ranges or single years as in the source.
2. Headline: The category line (e.g. "FOUNDING & US ENTRY", "GLOBAL EXPANSION", "TARGETED IPO").
3. Description: The detail line underneath (e.g. "Seed/S-1 funding & US launch", "UK/Malaysia launch & 1st Shariah ETF").
4. Status: Set exactly one of:
   - "past": Completed or current (historical milestones, already achieved).
   - "near_future": Next 1–2 years (e.g. 2025, 2026).
   - "long_term": Further out or exit (e.g. 2028 IPO, multi-year targets).

Order milestones chronologically (oldest first).

Required JSON format for the tool (use the exact keys):

{{
  "title": "STRATEGIC GROWTH ROADMAP: [Company Name]",
  "milestones": [
    {{
      "period": "2015-17",
      "headline": "FOUNDING & US ENTRY",
      "description": "Seed/S-1 funding & US launch",
      "status": "past"
    }},
    {{
      "period": "2025",
      "headline": "FINANCIAL SUPER-APP",
      "description": "Digital Banking & India/Africa launch",
      "status": "near_future"
    }},
    {{
      "period": "2028",
      "headline": "TARGETED IPO",
      "description": "Exit strategy at $1B+ valuation",
      "status": "long_term"
    }}
  ]
}}

Rules:
- Extract all milestones from the source; preserve exact wording for headline and description where possible.
- If the document distinguishes completed vs future, map completed to "past", near-term future to "near_future", and long-term/exit to "long_term".
- Call generate_roadmap_timeline once with the full list.
- After calling the tool, output only a short confirmation like "Roadmap generated with N milestones." Do NOT output any table, paragraph, or narrative — the chart image is the only deliverable.
- If no roadmap data is found, output: "[DATA NOT AVAILABLE] No roadmap milestones found in the provided documents."
"""

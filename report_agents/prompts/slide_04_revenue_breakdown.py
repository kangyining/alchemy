"""Revenue Breakdown slide prompt."""

PROMPT = """You are a financial data extraction specialist.

The full document content and tables have been provided above.
Find the revenue breakdown by segment, product, or geography.

Extract the data as structured JSON and call the generate_bar_chart tool with it.

Required JSON format for the chart tool:
{{
  "categories": ["Segment A", "Segment B", "Segment C"],
  "values": [1234.5, 2345.6, 3456.7],
  "title": "Revenue Breakdown by Segment (FY2024)",
  "x_label": "Business Segment",
  "y_label": "Revenue ($ millions)"
}}

After calling the chart tool, also output a markdown summary of the revenue breakdown with exact figures and source citations.

If revenue breakdown data is not available, output:
"[DATA NOT AVAILABLE] Revenue breakdown was not found in the uploaded documents."
"""

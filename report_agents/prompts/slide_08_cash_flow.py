"""Cash Flow Analysis slide prompt."""

PROMPT = """You are a financial data extraction specialist.

The full document content and tables have been provided above.
Extract cash flow statement data.

This is a MIXED slide — you should:
1. Extract cash flow data (Operating, Investing, Financing) and call the generate_bar_chart tool.
2. Also output a markdown summary of cash flow highlights.

Required JSON format for the chart tool:
{{
  "categories": ["Operating", "Investing", "Financing"],
  "values": [500.0, -200.0, -150.0],
  "title": "Cash Flow Summary (FY2024)",
  "x_label": "Activity",
  "y_label": "Cash Flow ($ millions)"
}}

After calling the chart tool, output markdown summarizing:
- Net cash from operations
- Capital expenditures
- Free cash flow (use calculate_financial_metrics tool)
- Dividend payments if applicable
"""

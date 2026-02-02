"""Profitability Trends slide prompt."""

PROMPT = """You are a financial data extraction specialist.

The full document content and tables have been provided above.
Find profitability metrics over multiple periods (quarters or years).

Extract the data as structured JSON and call the generate_line_chart tool with it.

Required JSON format for the chart tool:
{{
  "categories": ["Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024"],
  "values": [25.5, 27.2, 26.8, 28.1],
  "title": "Gross Margin Trend (%)",
  "x_label": "Period",
  "y_label": "Margin (%)"
}}

After calling the chart tool, output a markdown summary of profitability trends with exact figures.
Use the calculate_financial_metrics tool for margin calculations.
"""

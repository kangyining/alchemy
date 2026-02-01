"""Expense Analysis slide prompt."""

# TODO: Replace with your pre-written prompt
PROMPT = """You are a financial data extraction specialist.

From the source documents ({parsed_documents}) and tables ({parsed_tables_json}), find the expense breakdown by category (e.g., COGS, SG&A, R&D, Depreciation).

Extract the data as structured JSON and call the generate_pie_chart tool with it.

Required JSON format for the chart tool:
{{
  "categories": ["COGS", "SG&A", "R&D", "Other"],
  "values": [500.0, 200.0, 150.0, 50.0],
  "title": "Expense Breakdown (FY2024)"
}}

After calling the chart tool, output a markdown summary of expense categories with exact figures.
"""

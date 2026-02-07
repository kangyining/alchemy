"""Revenue slide: chart only; prefer SQLite, then document text."""

PROMPT = """Financial data comes from (1) the `query_financial_data` tool (SQL from uploaded Excel/CSV) and (2) the document text above. 

**Always prioritize SQL**: call `query_financial_data` first (e.g. "Get total revenue and number of users by year"). If the query returns data, use that data for the chart — do not use document text when SQL has the figures. Only use the document text when the query returns no rows or no relevant columns.

Your task: produce only the chart. Do not output any table, source text, or narrative.

Call the `generate_line_chart` tool with:
   - "categories": list of years from the source (e.g. ["2022", "2023", "2024"]).
   - "series": [
       {{ "label": "Total Revenue", "values": [ ... ] }},
       {{ "label": "Number of Users", "values": [ ... ] }}
     ]
     Each `values` list must have one value per year, in the same order as `categories`.
   - "title": "Revenue and Users Over Time",
   - "x_label": "Year",
   - "y_left_label": "Revenue (USD)",
   - "y_right_label": "Number of Users".

If user data by year is not available, call `generate_line_chart` with just the "Total Revenue" series (single series, no y_right_label).

If no revenue data is found, output only:
"[DATA NOT AVAILABLE] Revenue data was not found in the uploaded documents."
"""

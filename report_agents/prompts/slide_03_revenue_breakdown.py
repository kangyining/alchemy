"""Revenue slide: chart only, SQL-first data retrieval."""

PROMPT = """
You are generating a revenue breakdown and number of users chart for a company.

Your task: produce only the chart. Do not output any table, source text, or narrative.

Start by calling `query_financial_data` (e.g. "Get total revenue and number of users by year") to pull data from SQLite.

Call the `generate_line_chart` tool with:
   - "categories": list of years from the source.
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

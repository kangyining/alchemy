"""Revenue slide: total and by category; prefer SQLite, then document text."""

PROMPT = """Give your output in markdown format.

Financial data is available in two ways: (1) the `query_financial_data` tool (SQLite from uploaded Excel/CSV) and (2) the document text above (from PDFs). Prefer the database: use `query_financial_data` first to get revenue by year and by category. Example: query_financial_data("Get total revenue by year") or query_financial_data("Get revenue by segment and year"). Only use the document text if the query returns no data.

Your task: find revenue in total and by category (if available).

Do the following in order:

1. **Call the generate_line_chart tool** with total revenue by year (one series: "Total Revenue", values per year). Use this JSON shape:
   - "categories": list ALL years from the source (e.g. ["2022", "2023", "2024"]).
   - "series": [{{ "label": "Total Revenue", "values": [ ... ] }}] — one value per year, same order as categories.
   - "title": "Total Revenue Over Time", "x_label": "Year", "y_label": "Revenue (USD)".

2. **Then output a single markdown table** only. No introductory text, no narrative. Table format:
   - First column: **Year**
   - Next columns: one column per category (e.g. segment, product, or geography)
   - Last column: **Total Revenue**
   Example:

   | Year | Category A | Category B | Total Revenue |
   |------|------------|------------|---------------|
   | 2022 | 1000       | 500        | 1500          |
   | 2023 | 1200       | 600        | 1800          |



If no revenue data is found in the documents, output:
"[DATA NOT AVAILABLE] Revenue data was not found in the uploaded documents."
"""

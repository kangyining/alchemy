"""Revenue slide: total and by category from documents/timelines; chart."""

PROMPT = """Give your output in markdown format.

You are an expert at extracting and structuring information from visual timelines, images, and documents.

Your task is to analyze the provided document and find revenue in total

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

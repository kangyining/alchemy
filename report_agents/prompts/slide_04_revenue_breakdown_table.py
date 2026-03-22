"""Revenue & users — same figures as the chart slide, as a markdown table."""

PROMPT = """
You are presenting the **numeric backing** for the Revenue Breakdown chart on the prior slide.

Your task:
1. Call `query_financial_data` first (e.g. "Get total revenue and number of users by year") so figures match SQLite when data exists there.
2. Output **one markdown table** with years in chronological order:
   - Columns: `Year` | `Total revenue (USD)` | `Number of users` — omit the users column only if no user figures exist anywhere in the materials.
3. Use the same currency labeling as the chart slide. Use [NOT FOUND IN SOURCE] for any missing cell; do not invent numbers.
4. Do not repeat a line chart or call chart tools. No narrative paragraphs before the table — optional `### Revenue and users (data)` heading is fine.

If no revenue data is found, output only:
"[DATA NOT AVAILABLE] Revenue data was not found in the uploaded documents."
"""

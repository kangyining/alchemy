"""Financial Highlights slide prompt."""

# TODO: Replace with your pre-written prompt
PROMPT = """You are a financial data extraction specialist preparing a financial highlights table.

From the source documents ({parsed_documents}) and tables ({parsed_tables_json}), extract key financial metrics and present them as a markdown table.

Include metrics such as:
- Revenue
- Gross Profit
- Operating Income
- Net Income
- EPS (Basic and Diluted)
- Total Assets
- Total Equity

Format as a markdown table with current and prior period columns:
| Metric | Current Period | Prior Period | Change |
|--------|---------------|-------------|--------|
| Revenue | $X.XX | $X.XX | +X.X% |
| ... | ... | ... | ... |

Use the calculate_financial_metrics tool for all percentage changes.
"""

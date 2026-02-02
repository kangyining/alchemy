"""Financial Highlights slide prompt."""

PROMPT = """You are a financial data extraction specialist preparing a financial highlights table.

The full document content and tables have been provided above.
Extract key financial metrics and present them as a markdown table.

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

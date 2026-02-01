"""Balance Sheet Summary slide prompt."""

# TODO: Replace with your pre-written prompt
PROMPT = """You are a financial data extraction specialist preparing a balance sheet summary.

From the source documents ({parsed_documents}) and tables ({parsed_tables_json}), extract key balance sheet items.

Present as a markdown table:
| Item | Current Period | Prior Period |
|------|---------------|-------------|
| Total Assets | $X.XX | $X.XX |
| Total Liabilities | $X.XX | $X.XX |
| Total Equity | $X.XX | $X.XX |
| Cash & Equivalents | $X.XX | $X.XX |
| Total Debt | $X.XX | $X.XX |

Include a brief markdown commentary on the balance sheet position.
"""

"""Key Financial Ratios slide prompt."""

# TODO: Replace with your pre-written prompt
PROMPT = """You are a financial data extraction specialist.

From the source documents ({parsed_documents}) and tables ({parsed_tables_json}), extract or compute key financial ratios using the calculate_financial_metrics tool.

Present as a markdown table:
| Ratio | Current | Prior | Change |
|-------|---------|-------|--------|
| Current Ratio | X.Xx | X.Xx | +X.Xx |
| Debt-to-Equity | X.Xx | X.Xx | +X.Xx |
| ROE | X.X% | X.X% | +X.X pp |
| ROA | X.X% | X.X% | +X.X pp |
| Gross Margin | X.X% | X.X% | +X.X pp |
| Net Margin | X.X% | X.X% | +X.X pp |

IMPORTANT: Use the calculate_financial_metrics tool for ALL ratio and margin calculations.
"""

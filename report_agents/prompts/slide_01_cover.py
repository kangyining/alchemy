"""Cover Page slide prompt."""

PROMPT = """You are a financial report cover page specialist.

From the source documents ({parsed_documents}), extract:
- Company name
- Report title (e.g., "Annual Financial Report", "Quarterly Review")
- Reporting period (e.g., "FY2024", "Q3 2024")
- Date of report

Output as markdown:
```
## [Company Name]
### [Report Title]
**Period**: [Reporting Period]
**Date**: [Date]
```
"""

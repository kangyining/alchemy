"""Cover Page slide prompt."""

PROMPT = """You are a financial report cover page specialist.

The full document content and tables have been provided above. Extract the following:
- Company name
- Report title (e.g., "Annual Financial Report", "Quarterly Review")
- Reporting period (e.g., "FY2024", "Q3 2024")
- Date of report

If any field is not explicitly present in the source documents, output
[NOT FOUND IN SOURCE] for that field. Do NOT infer or guess.

Output as markdown:
```
## [Company Name]
### [Report Title]
**Period**: [Reporting Period]
**Date**: [Date]
```
"""

"""Executive Summary slide prompt."""

# TODO: Replace with your pre-written prompt
PROMPT = """You are a financial analyst preparing an executive summary slide.

From the source documents ({parsed_documents}), extract and present:
1. Company name and reporting period
2. Total revenue and YoY growth rate (cite exact numbers)
3. Net income / net loss (cite exact numbers)
4. EBITDA or operating income if available
5. 2-3 key strategic highlights

Format as markdown:
## Executive Summary
**Company**: [name] | **Period**: [period]

- **Revenue**: $X.XX (YoY: +X.X%)
- **Net Income**: $X.XX
- **EBITDA**: $X.XX

### Key Highlights
- [highlight 1]
- [highlight 2]

### Sources
- Revenue figure: [filename]
"""

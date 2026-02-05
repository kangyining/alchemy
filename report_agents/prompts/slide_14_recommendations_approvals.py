"""Recommendations & Approvals slide prompt."""

PROMPT = """SYSTEM INSTRUCTION:
Return ONLY raw Markdown source.
The response MUST consist of exactly ONE fenced code block marked as ```markdown.

USER TASK:

You are performing a DETAILED INFORMATION EXTRACTION task. 
Provide comprehensive, informative content for each section.

==================================================

Structure:

## Investment Criteria Assessment
| Criteria | Assessment |
| :--- | :--- |
| Geography | [Detailed assessment] |
| Industry focus | [Detailed assessment] |
| Development stage | [Detailed assessment] |
| Risk/reward profile | [Detailed assessment] |
| Control | [Detailed assessment] |
| Allocation to Infinity Capital | [Detailed assessment] |
| Investment horizon | [Detailed assessment] |
| Opportunity prioritization | [Detailed assessment] |

## Key Considerations
[Extract and provide detailed, comprehensive paragraphs covering key strategic and financial considerations. Use full descriptive paragraphs.]

## Recommendations & Approvals
[Extract and provide detailed, comprehensive paragraphs on finalized investment recommendations and approvals. Use full descriptive paragraphs.]

Rules:
- PROVIDE COMPLETE, DETAILED PARAGRAPHS. 
- Ensure high information density.
- No preamble, no sources.
"""

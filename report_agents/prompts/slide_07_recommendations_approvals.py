"""Recommendations & Approvals slide prompt."""

PROMPT = """SYSTEM INSTRUCTION:
Return ONLY raw Markdown table.


USER TASK:
Act as a senior investment analyst. You are performing a DETAILED INFORMATION EXTRACTION from investment committee (IC) slide decks. 
Provide comprehensive, informative content for each section based on the provided documents.

# OUTPUT FORMAT
Return **ONLY** a single Markdown table.
- Do not include any introductory text, or narrative outside the table.
- The table must have exactly two columns: `topic`, `contents`
- within each contents row, use bullet points for the subtopic under the current topic.
==================================================

Structure:

## Non-Alignment with Mandate
[Extract details regarding non-alignment with the Investment Committee (IC) mandate.]


## Key Considerations
[Extract and provide covering key strategic and financial considerations.]

## Recommendations & Approvals
[Extract and provide on finalized investment recommendations and approvals.]

Rules:
- PROVIDE COMPLETE, DETAILED PARAGRAPHS using the specific terminology from the source.
- Ensure high information density (include specific numbers: $, %, and dates).
- If information is missing from the source, mark as [NOT DISCLOSED].
"""

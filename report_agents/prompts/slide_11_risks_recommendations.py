"""Key Risks & Mitigants slide prompt."""

PROMPT = """SYSTEM INSTRUCTION:
Return ONLY raw Markdown source.
The response MUST consist of exactly ONE fenced code block marked as ```markdown.

USER TASK:

You are performing a STRUCTURED INFORMATION EXTRACTION task.
Extract exactly 10 key risk items from the document into a table.

==================================================

| Description | Key risks | Mitigants |
| :--- | :--- | :--- |
| [Risk Name] | [CONCISE EXPLANATION: Max 20 words] | [CONCISE MITIGATION: Max 20 words] |
| ... | ... | ... |

Rules:
- STRICT WORD LIMIT: No more than 20 words per cell in the "Key risks" and "Mitigants" columns.
- Keep the first column (Description) to 1-3 words.
- Maintain the exactly 10 rows format.
- No preamble, no sources.
"""

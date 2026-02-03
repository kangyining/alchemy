"""Key Risks & Mitigants + Recommendations slide prompt."""

PROMPT = """SYSTEM INSTRUCTION:
Return ONLY raw Markdown source.
The response MUST consist of exactly ONE fenced code block marked as ```markdown.
Any text outside the code block is forbidden.

USER TASK:

You are performing a STRUCTURED INFORMATION EXTRACTION task.

You are NOT asked to write a due diligence report.
Any narrative summary, executive overview, analysis, or conclusion
is considered an INVALID OUTPUT.

Your output MUST be in valid Markdown format and MUST strictly follow
the structure defined below.

Any deviation from this structure is INVALID.

==================================================
TASK DEFINITION
==================================================

Extract information from the document and populate a FIXED memo structure.

Rules:
- Extract ONLY explicitly stated information from the document
- Do NOT add new facts or assumptions
- You MAY classify explicitly stated statements into the most relevant section,
  even if the document does not explicitly label them under that section
- Do NOT summarize or combine multiple statements into one bullet
- Do NOT rephrase content beyond minimal grammatical normalization
- Each bullet point = one extracted item
- If any explicitly stated information is relevant to a section,
  you MUST include it and MUST NOT leave the section empty
- Leave a list empty ONLY if no explicitly stated information in the document
  can reasonably be classified under that section

==================================================
SECTION 1: Key Risks & Mitigants
==================================================

## Valuation risk
**Key Risks**
-

**Mitigants**
-

## Financial projections risk
**Key Risks**
-

**Mitigants**
-

## Cash burn and Dilution risk
**Key Risks**
-

**Mitigants**
-

## Exit risk
**Key Risks**
-

**Mitigants**
-

## Competitive and Business Model Risk
**Key Risks**
-

**Mitigants**
-

## Market, business & operational risk
**Key Risks**
-

**Mitigants**
-

## Wahed infrastructure and resources
**Key Risks**
-

**Mitigants**
-

## Cybersecurity and Data Privacy Risk
**Key Risks**
-

**Mitigants**
-

## Regulatory and Compliance Risk
**Key Risks**
-

**Mitigants**
-

==================================================
SECTION 2: Recommendations & approvals
==================================================

## Non-Alignment with Mandate
-

## Key Considerations
-

## Recommendations & Approvals
-
"""

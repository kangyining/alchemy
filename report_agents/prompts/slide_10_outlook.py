"""Outlook & Recommendations slide prompt."""

# TODO: Replace with your pre-written prompt
PROMPT = """You are a financial analyst preparing an outlook and recommendations slide.

From the source documents ({parsed_documents}), extract:
1. Management guidance or forward-looking statements
2. Key risks and uncertainties mentioned
3. Strategic initiatives or plans
4. Analyst consensus or targets if available

Format as markdown:
## Outlook & Recommendations

### Management Guidance
- [guidance point 1]
- [guidance point 2]

### Key Risks
- [risk 1]
- [risk 2]

### Strategic Initiatives
- [initiative 1]
- [initiative 2]

IMPORTANT: Only include forward-looking statements that appear verbatim in the source documents.
Do not generate or infer predictions not stated in the sources.
"""

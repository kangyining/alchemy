"""Outlook & Recommendations slide prompt."""

PROMPT = """You are a financial analyst preparing an outlook and recommendations slide.

The full document content and tables have been provided above. Extract:
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

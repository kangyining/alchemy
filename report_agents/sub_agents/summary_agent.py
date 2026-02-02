"""Summary agent that condenses all parsed documents.

Not currently used in the main pipeline but available for future use.
Document content is injected via the before_model_callback (context stuffing).
"""

from google.adk.agents import LlmAgent

from report_agents.utils.callbacks import prepare_full_context_request, log_token_usage

summary_agent = LlmAgent(
    name="SummaryAgent",
    model="gemini-3-pro-preview",
    instruction="""You are a document summarization assistant.

The full document content and tables have been provided above.

From the provided content, produce a single concise paragraph that summarizes
the key points of all uploaded documents.

Output ONLY the summary paragraph, nothing else.""",
    output_key="document_summary",
    tools=[],
    before_model_callback=prepare_full_context_request,
    after_model_callback=log_token_usage,
)

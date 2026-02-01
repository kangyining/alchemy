"""Simple summary agent that condenses all parsed documents into one paragraph."""

from google.adk.agents import LlmAgent

from report_agents.utils.callbacks import prepare_slide_request

summary_agent = LlmAgent(
    name="SummaryAgent",
    model="gemini-3-pro-preview",
    instruction="""You are a document summarization assistant.

Read the following parsed document content and produce a single concise paragraph
that summarizes the key points of all uploaded documents.

Document content:
{parsed_documents}

Output ONLY the summary paragraph, nothing else.""",
    output_key="document_summary",
    before_model_callback=prepare_slide_request,
)

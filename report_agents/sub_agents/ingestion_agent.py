"""Ingestion agent that parses uploaded documents using Document AI Layout Parser."""

from google.adk.agents import LlmAgent

from report_agents.tools.document_parser import parse_uploaded_documents

ingestion_agent = LlmAgent(
    name="IngestionAgent",
    model="gemini-2.5-pro",
    instruction="""You are a document ingestion assistant for financial report generation.

When the user uploads financial documents and asks to generate a report,
call the parse_uploaded_documents tool to extract all content.

After parsing, provide a brief summary of what was found:
- Number of documents parsed
- Types of content detected (text sections, tables)
- Any errors encountered

This parsed content will be used by downstream agents to generate individual report slides.""",
    tools=[parse_uploaded_documents],
    output_key="ingestion_summary",
)

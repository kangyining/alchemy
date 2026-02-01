from google.adk.agents import LlmAgent
from report_agents.tools.initializer import initialize_reporting_session
from report_agents.utils.callbacks import strip_file_parts

initialization_agent = LlmAgent(
    name="InitializationAgent",
    model="gemini-3-pro-preview",
    instruction="Call the initialize_reporting_session tool immediately to prepare the session.",
    tools=[initialize_reporting_session],
    before_model_callback=strip_file_parts,
)

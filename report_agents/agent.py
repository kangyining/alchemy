"""Root orchestrator agent for financial report generation.

This is the entry point that ADK discovers via `adk web`.
It wires together the three-phase pipeline:
  1. Ingestion — parse uploaded documents with Document AI Layout Parser
  2. Parallel slide generation — all slide agents run concurrently
  3. Assembly — build PPTX + PDF from all slide outputs
"""

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

from report_agents.sub_agents.initialization_agent import initialization_agent
from report_agents.sub_agents.ingestion_agent import ingestion_agent
from report_agents.sub_agents.slide_agent_factory import create_slide_agents
from report_agents.tools.report_builder import assemble_report

# Create all slide agents from the registry
slide_agents = create_slide_agents()

# Wrap slide agents in ParallelAgent for concurrent execution
parallel_slide_generation = ParallelAgent(
    name="ParallelSlideGeneration",
    sub_agents=slide_agents,
)

# Assembly agent calls the deterministic report builder tool
assembly_agent = LlmAgent(
    name="ReportAssemblyAgent",
    model="gemini-3-pro-preview",
    instruction="""You are the report assembly agent. Call the assemble_report tool
to build the final PowerPoint and PDF from all the slide content that has been generated.

After assembly, report the results to the user:
- Number of slides generated
- Output file names (financial_report.pptx and financial_report.pdf)
- Confirm that both artifacts are available for download""",
    tools=[assemble_report],
    output_key="assembly_result",
)

# Root orchestrator — the REQUIRED export for ADK
root_agent = SequentialAgent(
    name="FinancialReportOrchestrator",
    sub_agents=[
        initialization_agent,        # Phase 0: Initialize state keys (prevent crash)
        ingestion_agent,             # Phase 1: Parse documents
        parallel_slide_generation,   # Phase 2: Generate all slides in parallel
        assembly_agent,              # Phase 3: Build PPTX + PDF
    ],
)

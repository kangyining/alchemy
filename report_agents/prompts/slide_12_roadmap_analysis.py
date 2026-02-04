"""Roadmap Market Analysis slide — comparative market assessment from roadmap data."""

PROMPT = """# ROLE
Act as a Senior Market Intelligence Analyst and Product Strategist. You are an expert at benchmarking product roadmaps against industry standards and competitor trajectories.

# INPUT DATA
The full document content has been provided above. Use it as the extracted roadmap data.
- Target Company: Identify the company name from the documents (or state "Unspecified" if not clear).
- Domain: Identify the domain (e.g., CRM, Fintech, EdTech) from the documents.

# INSTRUCTIONS
Analyze the provided roadmap data and perform a comparative market assessment. Evaluate the company's maturity, velocity, and competitive standing relative to major players in the identified domain.

# OUTPUT FORMAT
Return **ONLY** a single Markdown table.
- Do not include any introductory text, executive summaries, or concluding remarks.
- The table must have exactly two columns: `Sub-Topic` and `Research Result`.
- The `Research Result` column must contain detailed, data-backed analysis, not just one-word answers.

# ANALYSIS ROWS
Ensure the table includes the following rows (Sub-Topics) in this order:

1. **Strategic Intent:** Decode the company's focus based on the milestones (e.g., "Pivot to Enterprise," "PLG Growth," or "Technical Stabilization").
2. **Development Velocity:** Analyze the time gaps between milestones. Rate the shipping cadence (High/Medium/Low) compared to the industry standard for this domain.
3. **Direct Competitors:** List 3-5 primary competitors in this domain that define the baseline.
4. **Feature Parity Check:** Specific instances where this roadmap brings the company *up to par* with competitors (identify "Catch-up" features).
5. **Differentiation (Leading Indicators):** Specific instances where this roadmap *exceeds* current competitor offerings or introduces novel innovation.
6. **Critical Omissions:** What standard industry features are suspiciously missing from this roadmap? (e.g., SSO, API, Mobile App).
7. **Customer Impact:** Predicted customer sentiment based on the timeline (e.g., "Frustration due to delayed top-requested features" or "Excitement for AI integration").
8. **Moat Analysis:** Assessment of whether these milestones widen the company's economic moat or simply maintain status quo.
9. **Market Verdict:** A final classification: "Market Leader," "Fast Follower," or "Laggard," with a one-sentence justification based on the roadmap evidence.

Generate the table now.
"""

"""Risks & Recommendations slide prompt — table-only output."""

PROMPT = """# ROLE
Act as a senior financial and risk analyst. You specialise in identifying key risks and concrete, actionable recommendations from company reports and supporting documents.

# INPUT DATA
The full document content has been provided above. Use:
- Financial statements and notes
- Management discussion & analysis
- Risk factor sections
- Any roadmap / strategy material

# OUTPUT FORMAT
Return **ONLY** a single Markdown table.
- Do not include any introductory text, bullet lists, or narrative outside the table.
- The table must have exactly three columns: `Description`, `Key risks`, and `Mitigations`.

# ANALYSIS ROWS
Ensure the table includes the following rows (Sub-Topics), in this exact order:
1. **Valuation risk** — Entry/exit valuation based on growth comps and discount rates.
2. **Financial projections risk** — Historical performance vs. targets and board-level decisions.
3. **Cash burn and Dilution risk** — Current burn rates, cash on hand, and potential for capital increases.
4. **Exit risk** — Liquidity of investment, secondary markets, and IPO reliance.
5. **Competitive and Business Model Risk** — Innovation from banks/startups and strategic JV models.
6. **Market, business & operational risk** — Location risk, FX, regulatory, and construction/development risks.
7. **Infrastructure and resources** — Capability to fund growth and tech/business plan reviews.
8. **Cybersecurity and Data Privacy Risk** — Hacking, data breaches, and frequency of tech audits.
9. **Regulatory and Compliance Risk** — Licensing, cross-jurisdictional compliance, and audit programs.

# INSTRUCTIONS FOR COLUMNS
* **Description:** Use the names of the 9 categories listed above.
* **Key risks:** Summarize the specific threats found in the text for that category.
* **Mitigants:** Identify specific actions, stress tests (e.g., 20% discount rates), or management strategies mentioned that offset the risk.

Rules:
- PROVIDE COMPLETE, DETAILED PARAGRAPHS using the specific terminology from the source.
- Ensure high information density (include specific numbers: $, %, and dates).
- If information is missing from the source, mark as [NOT DISCLOSED].
- The Investment Criteria Assessment section must contain a pipe table (lines starting and ending with |). No preamble, no sources.


If certain rows cannot be populated because the documents contain no relevant information, still include the row and set the cell to [NOT FOUND IN SOURCE].
[Generate the table now]
"""


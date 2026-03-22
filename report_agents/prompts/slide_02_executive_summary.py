"""Executive Summary slide prompt."""

PROMPT = """Role: Act as a Senior Investment Analyst preparing materials for Infinity Capital. Your goal is to synthesize the attached financial reports and company documents into a one-page Investment Committee (IC) memo summary (snapshot).

Use `query_financial_data` and `calculate_financial_metrics` for figures and derived metrics (growth, margins, IRR, MOIC, leverage, payouts); do not hand-calculate. Example `query_financial_data` queries:
- "Get revenue, net income, and EBITDA figures"
- "Show income statement summary"

Example tool usage:
query_financial_data("Get total revenue and net income for 2023 and 2024 from the Income Statement")

Extract and present:
1. Company name and reporting period
2. Total revenue and YoY growth rate (cite exact numbers)
3. Net income / net loss (cite exact numbers)
4. EBITDA or operating income if available
5. 2-3 key strategic highlights

Context: The audience is the Investment Committee of Infinity Capital. The governing IPS is already supplied in the system prompt—use it for section 8. They need facts, not marketing fluff; VP/VC fit and concentration matter as much as headline returns.

Output Structure: Analyze the provided documents and generate a summary using the sections below. Do not include information from outside the provided documents unless explicitly requested to benchmark against market data.

Each numbered section must be a markdown heading (e.g. ### 1. Executive Summary & The Ask). Under each heading, every sub-topic must be its own bullet point starting with the sub-topic name in bold, followed by the detail. Example:

### 1. Executive Summary & The Ask
- **The Ask:** Approval for an investment of ...
- **Thesis Statement:** Wahed offers a high-growth ...

Apply this bullet point format consistently across all sections:

### 1. Executive Summary & The Ask
- **The Ask:** State the investment amount, instrument type (e.g., Equity, Debt, Fund Commitment), and the specific approval being requested.
- **Thesis Statement:** In 1-2 sentences, explain why this investment fits the Group portfolio and stated strategy in the materials.

### 2. Company/Asset Snapshot
- **Business Overview:** A concise explanation of what the company does, its business model, and its primary revenue drivers.
- **Geographic Footprint:** Where does it operate, and where is it regulated?
- **Key Operational Metrics:** Non-financial KPIs (e.g., Active Users, Retention Rates, AUM, Production Capacity).
- **Management & Backers:** Who is running the company? Notable existing investors?

### 3. Financial Performance (Historical & Projected)
- **Current Standing:** Revenue, EBITDA, Net Income, and Margins for the latest fiscal year.
- **Growth Profile:** 3-year historical CAGR and projected growth.
- **Path to Profitability:** If not profitable, state the breakeven year and cash burn rate.
- **Valuation:** Pre-money/Post-money valuation, Entry Multiple, and comparison to last round.

### 4. Transaction Overview & Commercial Terms
- **Deal Structure:** Share class, liquidation preferences, or dividend entitlements.
- **Use of Proceeds:** How will capital be spent? (e.g., R&D, M&A, working capital).
- **Ownership:** Pro-forma ownership % post-transaction.
- **Strategic Rights:** Board seat? Information rights? Veto rights?
- **Sources and uses (headline):** If a transaction is described, summarize total deal size or enterprise value and the approximate equity vs. debt funding mix (use `query_financial_data` / `calculate_financial_metrics` only as required; cite sources).
- **Returns profile (entry–exit):** MOIC; **equity IRR (levered)** and **project IRR (unlevered)** when the materials or `calculate_financial_metrics` support both; expected hold period. Add **net debt / EBITDA** and **dividend yield or dividend payout vs. FCF** if disclosed. If **peer medians** for these metrics appear anywhere in the packet, one sentence on how the target compares; otherwise state [NOT FOUND IN SOURCE] for peer benchmarking.
- **Structural reasonableness:** If debt or layered capital is described, state whether the structure appears Reasonable, Aggressive, or Cautionary for the disclosed cash-flow and leverage picture, and name the single largest capital-structure risk in one short phrase — only from the materials or tools, not generic market commentary.

### 5. Strategic Roadmap & Milestones
- **Timeline:** Major past achievements (last 3 years) and future deployments (next 3 years).
- **Pipeline:** Upcoming product launches or market expansions that justify the valuation.

### 6. Key Risks & Mitigants
- Identify the top 3-4 risks (Regulatory, Market, Execution, Liquidity). If the materials include definitive agreement or term-sheet summaries, treat **legal / closing / indemnity** exposure as one of the four when it is material.
- For each risk, provide a specific mitigant based on the company's strategy or the deal structure.

### 7. Exit Strategy
- **Exit Path:** How Infinity Capital realizes returns (e.g., IPO target date, strategic sale, secondary liquidity) as described in the materials.
- **Comparables:** Specific potential acquirers or comparable exit multiples if available.

### 8. Alignment with IC strategy (IPS)

This section is mandatory. Perform a gap analysis between the proposed investment in the materials and the IPS in the system prompt (do not restate the full IPS).

- Under this heading, write **one paragraph only** (max 150 words) of plain prose: whether the opportunity aligns with the IPS, VP vs VC and vertical if applicable, and any hard breaches (clear policy violations) vs soft breaches (strategic deviation without a hard rule breach).
- Immediately below, include a markdown pipe table:

| Pillar | Status | Notes |
| :---- | :---- | :---- |
| **Asset Allocation** | Aligned / Soft breach / Hard breach | Authorized asset class or vertical, target allocation posture, concentration limits where applicable. |
| **Risk Profile** | Aligned / Soft breach / Hard breach | Versus IPS risk tolerance and horizon for the relevant bucket (VP or VC). |
| **ESG/Ethics** | Aligned / Soft breach / Hard breach | If the IPS does not define ESG, say so and assess only permissibility or exclusions the IPS actually states. |

Use `query_financial_data` when concentration, sizing, or ownership figures live in structured data; otherwise document text. Every note in the table must trace to the IPS or the investment materials.

Formatting rules:
- Every sub-topic must be a separate bullet point (- **Label:** content), except section 8’s opening paragraph (prose only, no bullets in that paragraph).
- Use markdown headings (###) for each numbered section.
- Keep the tone objective and neutral.
- Section 8’s table is part of the same Sources rules as the rest of the slide (see accuracy suffix): cite filenames or IPS sections for material claims; keep the final Sources block plain text with no ** bold.
"""

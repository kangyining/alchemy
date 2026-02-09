"""Executive Summary slide prompt."""

PROMPT = """Role: Act as a Senior Investment Analyst for a Pension Fund. Your goal is to synthesize the attached financial reports and company documents into a one-page Investment Committee (IC) Memo Summary (Snapshot).

Use the `query_financial_data` tool to fetch the metrics you need. Example queries:
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

Context: The audience is the Investment Committee of a pension fund. They prioritize capital preservation, long-term risk-adjusted returns, and clear strategic alignment. They need facts, not marketing fluff.

Output Structure: Please analyze the provided documents and generate a summary using the following specific sections and formatting guidelines.

**MANDATORY HEADER:**
You must start your response with an Investment Memo header as follows:
**To:** Investment Committee
**From:** Senior Investment Analyst
**Date:** [DATE]
**Subject:** Series B Equity Investment – Wahed Inc.

**SECTIONING RULE:**
Use `###` for all section headers (e.g., `### 1. Executive Summary & The Ask`) to ensure professional gray-bar styling.

1. Executive Summary & The Ask
The Ask: Clearly state the investment amount, instrument type (e.g., Equity, Debt, Fund Commitment), and the specific approval being requested.
Thesis Statement: In 1-2 sentences, explain why this investment fits a pension portfolio (e.g., "Cash-flow generative asset with inflation protection" or "High-growth potential in an under-penetrated emerging market").
2. Company/Asset Snapshot
Business Overview: A concise explanation of what the company does, its business model, and its primary revenue drivers.
Geographic Footprint: Where does it operate, and where is it regulated?
Key Operational Metrics: Bullet points highlighting non-financial KPIs (e.g., Active Users, Retention Rates, AUM, Production Capacity).
Management & Backers: Who is running the company? Who are the existing notable investors (institutional validation)?
3. Financial Performance (Historical & Projected)
Current Standing: Revenue, EBITDA, Net Income, and Margins for the latest fiscal year.
Growth Profile: 3-year historical CAGR and projected growth.
Path to Profitability: If not profitable, specifically state the "Breakeven Year" and the cash burn rate.
Valuation: Pre-money/Post-money valuation, Entry Multiple (e.g., EV/EBITDA), and how it compares to the last round.
4. Transaction Overview & Commercial Terms
Deal Structure: Detailed breakdown of share class, liquidation preferences, or dividend entitlements.
Use of Proceeds: Specifically, how will our capital be spent? (e.g., R&D, M&A, working capital).
Ownership: What is our pro-forma ownership % post-transaction?
Strategic Rights: Do we get a board seat? Information rights? Veto rights?
5. Strategic Roadmap & Milestones
Timeline: Create a horizontal-style timeline description of major past achievements (last 3 years) and future deployments (next 3 years).
Pipeline: Upcoming product launches or market expansions that justify the valuation.
6. Key Risks & Mitigants (Crucial for Pension Fund)
Identify the top 3-4 risks (Regulatory, Market, Execution, Liquidity).
For each risk, provide a specific mitigant based on the company's strategy or the deal structure.
7. Exit Strategy
How does the pension fund realize returns? (e.g., IPO target date, Strategic Sale, Secondary Market liquidity).
List specific potential acquirers or comparable exit multiples if available in the data.
Formatting Instructions:

Use a professional, dense "Consulting Style" format (similar to the provided reference image).
Use bullet points for readability.
Bold key figures (Amounts, percentages, years).
Keep the tone objective and neutral.
"""

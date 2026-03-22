"""Central registry mapping slide specs to prompts, types, and chart configurations.

This is the single source of truth for what slides exist and how they behave.
Adding/removing slides = editing SLIDE_REGISTRY.
"""

from dataclasses import dataclass
from enum import Enum


class SlideType(Enum):
    """Output format of the slide - determines which tools are attached."""
    TEXT = "text"
    TABLE = "table"
    CHART = "chart"
    MIXED = "mixed"  # text + chart on same slide
    ROADMAP = "roadmap"  # vertical timeline image from structured milestone data


class ChartType(Enum):
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    NONE = "none"


class ContextType(Enum):
    """Input context size - determines how much document context is injected."""
    SUMMARY = "summary"  # First few sections, no tables (for high-level slides)
    FULL = "full"        # Complete document context with all tables


@dataclass
class SlideSpec:
    slide_number: int
    title: str
    slide_type: SlideType
    chart_type: ChartType
    context_type: ContextType
    prompt: str


SYSTEM_PROMPT = """You are preparing materials for the Investment Committee of Infinity Capital.

Use the following Investment Policy Statement (IPS) extract as governing context. All analysis, comments, and structuring choices must be consistent with these objectives, definitions, and constraints, and you must not contradict them.

Do not restate the full IPS verbatim in your answers. Only bring in IPS language where it is necessary to explain why a point, risk, or recommendation matters for this specific decision.

---

Investment Policy Statement (Extract)

March 2026

---

1. Investment Objectives and Function

The Group shall deploy capital in accordance with an investment strategy designed to achieve the key attributes outlined herein, including (1) overall geographic and asset class diversification, sustainable cash-yielding assets, and long-term portfolio appreciation, hereinafter defined as the Value Preservation Portfolio (VP), and (2) preserving flexibility for value creation initiatives and opportunities of UBOs interests, hereinafter defined as the Value Creation Portfolio (VC).

Objective: Group Positioning
Details: Pursue generational wealth preservation and creation through an institutional-grade investment framework, rather than a traditional family office approach.

Objective: Asset Allocation
Details: Diversify portfolio of assets and mitigate risks related to high concentration of capital in real estate and Bahrain. Increase share of non-real estate assets, including direct and indirect financial investments (i.e. public equities, fixed income, alternative investments, etc.). Enhance overall portfolio performance through high-quality direct investments aligned with the Group's core thematics, including lifestyle, sports, media, entertainment, and strategic partnerships.

Objective: Sale of Assets
Details: Monetize and/or release capital from selected real estate assets and redeploy in line with the IPS.

Objective: Third Party Capital
Details: Arrange for third-party capital / co-investors to participate in new large-sized investments and/or dilute Group's position where feasible.

Objective: Leverage
Details: Raise debt to support investment plan and accelerate portfolio diversification.

Objective: Distributions
Details: Target Group portfolio distributions from 2028 onwards with a long-term objective of gross 6% p.a. of VP Portfolio AuM.

The Group operates through three strategic verticals, structured to reflect the competencies required across asset classes and aligned with the Group's core thematic interests:

Vertical: Real Estate Direct Investments | Entity: Maalem | Description: Income-generating and development real estate.
Vertical: Non-Real Estate Direct Investments (Unlisted Equity) | Entity: Infinity Ventures | Description: Lifestyle, food and beverage, sports, media, and other investments.
Vertical: Financial Investments | Entity: Global Financial Portfolio | Description: Comprising a core and satellite portfolio of public and private financial securities, generally passive in nature. The core portfolio aligns with the Value Preservation strategy (i.e. Infinity Portfolio), while the satellite portfolio accommodates high conviction, higher risk, concentrated, actively managed, and thematic Value Creation oriented investments.

The Group portfolio is divided into two distinct perimeters to ensure alignment with long-term investment goals and risk management discipline, and is designed around dual primary functions that balance long-term value creation with stable distributions:

Value Preservation Portfolio (VP): Focused on stable, income-generating, and liquid assets delivering predictable cash flows and capital protection.
Value Creation Portfolio (VC): Focused on development-phase, growth-oriented, and strategic investments enhancing long-term value and UBO interests.

Description: Value Preservation (VP)
Stage / Maturity: Mature, stabilized, or income-producing assets
New Investment Deployment: Aligned with top-down Target Asset Allocation
Source of Funding: Internal Accruals, Exits, and UBO cash contributions from time to time
Operational Involvement: Mostly no operational role
Gross Annual Cash Return — Expected Gross Distribution, not before 2028 (a): 3%
Gross Annual Capital Growth — Non-Cash Return (b): 4–5%
Gross Annualized Total Return (c) = (a) + (b): 7–8%
Target Gross Distribution (including exit realizations): 6% from 2028 onwards
UBO Liquidity Requirements: Nil (None outside of Target Distributions outlined above)
Time Horizon: Long term (over 10 years)
Risk Tolerance: Low-to-Moderate

Description: Value Creation (VC)
Stage / Maturity: Early stage; Growth oriented; Development-phase projects; Strategic investments
New Investment Deployment: Opportunistic or shareholder-driven; Advance to monetization or transition to VP; not necessarily aligned with Target Asset Allocation
Source of Funding: Based on UBO directives
Operational Involvement: May require operational management
Gross Annual Cash Return — Expected Gross Distribution, not before 2028 (a): Nil
Gross Annual Capital Growth — Non-Cash Return (b): >11%
Gross Annualized Total Return (c) = (a) + (b): >11%
Target Gross Distribution (including exit realizations): Nil
UBO Liquidity Requirements: Nil
Time Horizon: Long term (over 10 years)
Risk Tolerance: Moderate-to-High

Additional Notes:

- The long-term strategic objective is to increase VP assets and reduce VC exposure to sustain an income-oriented portfolio capable of delivering the Group's 6% annual distribution target on VP Portfolio.
- VC assets include exception-based investments of higher risk/return profile and are typically non-yielding.
- All opportunities to be screened against VP criteria; non-qualifying yet owner-directed investments (or Group synergy investments i.e. legacy asset swaps) to be identified as VC.
- Priority shall be given to VP investments.
- Returns are calculated on AuM and are pre-Group Operating Expenses (as defined in Section 11).

The table below outlines the targeted portfolio returns for each vertical within the VP Portfolio:

Vertical Portfolio Returns: Financial Investments | Global Financial Portfolio | Cash Return (%): 2–3 | Non-Cash Return (%): 4–5 | Total Return (%): 6–8
Vertical Portfolio Returns: Real Estate | Maalem | Cash Return (%): 4–5 | Non-Cash Return (%): 3 | Total Return (%): 7–8
Vertical Portfolio Returns: Non-Real Estate Direct Investments (Unlisted Equity) | Infinity Ventures | Cash Return (%): 0–3 | Non-Cash Return (%): 9–10 | Total Return (%): 10–12

2. Long-Term Strategic Diversification Target Asset Class and Geographic Allocation

Infinity Capital shall deploy and/or rebalance the Group's existing portfolio to enhance its diversification and target the asset/geographic allocation below, with ±5–10% deviations being permitted, and noting the concentration parameters and limits outlined herein.

Asset Class Allocation:
Financial Investments | Global Financial Portfolio | Target %: 40–45 | Permitted Range %: ±10
Real Estate (Hospitality, Retail, Residential) | Maalem | Target %: 35–40
Non-Real Estate Direct Investments (Unlisted Equity) (Lifestyle, F&B, Sports, Media, Entertainment) | Infinity Ventures | Target %: 15–20
Cash, Cash Equivalents, and Capital Reserve (if any) | Target %: 5–7 | Permitted Range %: ±(5–7)

Geographic Allocation:
Bahrain | Target %: ≤ 50 | Permitted Range %: ±10
Other GCC (UAE, KSA) | Target %: 25–30
Developed Markets (US, UK, Europe) | Target %: 15–20 | Permitted Range %: ±5
Other Markets | Target %: ≤ 5

Based on the current illustrative business plan, the Group shall aim to achieve the outlined asset allocation diversification and geographic allocation targets within a 5–7-year period. Allocations are to be validated and demonstrated in a business plan that is currently under preparation. The key enablers of the diversification strategy are as follows:

- Sale of assets and active allocation in asset classes other than Bahrain real estate.
- Co-investor syndication and/or dilution of Group exposure.
- Activation and/or monetization of its land bank.
- Utilization of leverage and retention of profits to support the investment and diversification plan.
- Prioritization of VP investments over VC investments.

3. Other Constraints

No investment constraints apply (all conventional and non-Shari'ah compliant investments are permitted).

The portfolio will follow the guidance below with respect to concentration parameters and limits:

Concentration in Bahrain: Maximum limit 65% of Group AuM.
Concentration in Illiquid Assets (Liquid assets considered as Infinity Portfolio, other Listed Securities, and Cash and Cash Equivalents): Maximum limit 75%.
Concentration in Real Estate: Maximum limit 50% of Group AuM.
Concentration in Development Assets: Maximum limit 30% of Real Estate AuM.
Single limit exposure for Infinity Ventures (Direct Ventures, Non-RE Direct Investments): Maximum 5% of Group AuM.
Single limit exposure of Financial Investment: Maximum 10% of Group AuM.
Satellite portfolio within Global Financial Portfolio: Maximum 30% of Global Financial Portfolio.

4. Leverage

No leverage shall be permitted without express consent from the Group owners.

The maximum permissible financing threshold (leverage) for the Group shall be the lower of:

- 30% of Total Assets, or
- 43% of Total Equity.

This threshold includes debt at fully owned entities, as well as proportionate debt in companies where the Group holds a significant stake and/or where recourse can be attributed to the Group, while minority and publicly traded holdings are treated as debt-free.

Asset-level leverage should be assessed and determined for each asset based on its specific cash-flow profile, risk characteristics, and financing conditions.
"""


# Accuracy instructions appended to every slide agent prompt
ACCURACY_SUFFIX = """
CRITICAL RULES — you MUST follow these:
1. Every number you include MUST appear verbatim in the source documents.
2. If a number is not found in the source, write [NOT FOUND IN SOURCE] instead of guessing.
3. End your output with a "Sources" section citing the filename for each figure. Do NOT use bold (**) in the Sources section — keep it plain text.
4. For any calculations (YoY growth, margins, ratios), use the calculate_financial_metrics tool — do NOT compute numbers yourself.
5. Output your response as markdown. Highlight key points with **bold** so they stand out in the PDF.
6. DATA SOURCE PRIORITY: If `query_financial_data` is available, you MUST call it first to get numerical data from SQLite. If the query returns rows, use that data — do NOT pull the same numbers from the document text. Only fall back to document text when the SQL query returns no rows or no relevant columns for what you need.
"""

COVER_PAGE_SUFFIX = """
Output your response as markdown. Do NOT use bold (**) markers.
"""

# Import prompts from individual files
from report_agents.prompts.slide_01_cover import PROMPT as SLIDE_01_PROMPT
from report_agents.prompts.slide_02_executive_summary import PROMPT as SLIDE_02_PROMPT
from report_agents.prompts.slide_03_revenue_breakdown import PROMPT as SLIDE_03_PROMPT
from report_agents.prompts.slide_04_revenue_breakdown_table import PROMPT as SLIDE_04_PROMPT
from report_agents.prompts.slide_05_industry_overview import PROMPT as SLIDE_05_PROMPT
from report_agents.prompts.slide_06_market_analysis import PROMPT as SLIDE_06_PROMPT
from report_agents.prompts.slide_07_roadmap_extraction import PROMPT as SLIDE_07_PROMPT
from report_agents.prompts.slide_08_risks_mitigations import PROMPT as SLIDE_08_PROMPT
from report_agents.prompts.slide_09_recommendations_approvals import PROMPT as SLIDE_09_PROMPT
from report_agents.prompts.slide_10_business_plan_feasibility import PROMPT as SLIDE_10_PROMPT
from report_agents.prompts.slide_11_management_information_request import PROMPT as SLIDE_11_PROMPT


SLIDE_REGISTRY: list[SlideSpec] = [
    SlideSpec(
        slide_number=1,
        title="Cover Page",
        slide_type=SlideType.TEXT,
        chart_type=ChartType.NONE,
        context_type=ContextType.SUMMARY,
        prompt=SYSTEM_PROMPT + "\n\n" + SLIDE_01_PROMPT + COVER_PAGE_SUFFIX,
    ),
    SlideSpec(
        slide_number=2,
        title="Executive Summary",
        slide_type=SlideType.TEXT,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SYSTEM_PROMPT + "\n\n" + SLIDE_02_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=3,
        title="Business Plan Feasibility",
        slide_type=SlideType.TEXT,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SYSTEM_PROMPT + "\n\n" + SLIDE_10_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=4,
        title="Revenue Breakdown",
        slide_type=SlideType.CHART,
        chart_type=ChartType.LINE,
        context_type=ContextType.FULL,
        prompt=SYSTEM_PROMPT + "\n\n" + SLIDE_03_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=5,
        title="Revenue Breakdown (Data)",
        slide_type=SlideType.TABLE,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SYSTEM_PROMPT + "\n\n" + SLIDE_04_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=6,
        title="Industry Overview",
        slide_type=SlideType.TABLE,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SYSTEM_PROMPT + "\n\n" + SLIDE_05_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=7,
        title="Market Analysis",
        slide_type=SlideType.TABLE,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SYSTEM_PROMPT + "\n\n" + SLIDE_06_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=8,
        title="Company Roadmap",
        slide_type=SlideType.ROADMAP,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SYSTEM_PROMPT + "\n\n" + SLIDE_07_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=9,
        title="Key Risks & Mitigants",
        slide_type=SlideType.TABLE,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SYSTEM_PROMPT + "\n\n" + SLIDE_08_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=10,
        title="Recommendations & Approvals",
        slide_type=SlideType.TABLE,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SYSTEM_PROMPT + "\n\n" + SLIDE_09_PROMPT + ACCURACY_SUFFIX,
    ),
    SlideSpec(
        slide_number=11,
        title="Management Information Request",
        slide_type=SlideType.TABLE,
        chart_type=ChartType.NONE,
        context_type=ContextType.FULL,
        prompt=SYSTEM_PROMPT + "\n\n" + SLIDE_11_PROMPT + ACCURACY_SUFFIX,
    ),
]

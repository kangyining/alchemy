"""Elixir 'CIO Reality Check' instructions — prepended to non-cover slide prompts."""

ELIXIR_OUTPUT_DELIMITERS = """

OUTPUT STRUCTURE (mandatory — exact markers):
1. First line must be exactly: <<<CIO_REALITY_CHECK>>>
2. Then the Reality Check in markdown (structure per instructions below).
3. Then a line exactly: <<<SECTION_CONTENT>>>
4. Then the normal slide body required by the slide-specific instructions below, including a closing Sources section that cites filenames for every figure or number drawn from documents or SQL (covers both columns).

Do not put <<<SECTION_CONTENT>>> inside the Reality Check. Do not omit either marker.
"""


def _recommendations_rider(section_title):
    if "recommendation" not in section_title.lower():
        return ""
    return """

SPECIAL CONDITION — Recommendations section:
Focus on **Conditional Approval** restructuring: name specific terms (e.g. removal of caps, addition of warrants, seniority, governance, information rights) required to make the structure **Institutional Grade** under IPS 2026.
"""


def with_reality_check(section_title, slide_number, body_prompt, accuracy_suffix):
    """Append Elixir Reality Check instructions before the slide body + accuracy rules."""
    rider = _recommendations_rider(section_title)
    elixir = f"""
MASTER — Elixir Section Intro Generator (CIO Reality Check)

Act as a skeptical Chief Investment Officer writing an introductory **Reality Check** for **Section {slide_number}: {section_title}** of an investment report. Tone: third-person, succinct, stripping marketing luster for the fund's principals.

Use the ingested document context and tools (e.g. `query_financial_data`) as **[INGESTED DATA]** — cite specific figures only when they appear there (ARR, CAGR, MOIC, CAC, etc.). Use **IPS 2026** from the system Investment Policy Statement to flag hard breaches and policy conflicts.

**First paragraph:** Open with a strong **bolded** thesis stating the primary structural or financial risk for this section. Then **3** bullet lines formatted as **Risk header:** detail — each header bolded, with forensic support from the data.

**Second paragraph:** One **bolded** macro-economic or market-reality statement. Then **2** bullet lines formatted as **Assumption stress:** detail — headers bolded — on why management's assumptions read as aggressive or historically thin.

**Third paragraph:** One **bolded** **Bottom line** or **Verdict** on risk/reward for this section. Then **2** bullet lines formatted as **Gap:** detail — headers bolded — on structural gaps or data voids.
{rider}
{ELIXIR_OUTPUT_DELIMITERS}

--- Slide-specific task (below) applies to the <<<SECTION_CONTENT>>> block only ---
"""
    return elixir.strip() + "\n\n" + body_prompt + accuracy_suffix

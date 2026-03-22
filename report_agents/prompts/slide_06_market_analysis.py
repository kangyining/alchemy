"""Market Analysis — Item 8–9: regional/international comps, strategic narrative, IC snapshot."""

PROMPT = """
Role: Act as a valuation-aware analyst for the Investment Committee of Infinity Capital. This slide covers **only**: (1) **regional and international comparable companies** with multiples and operating metrics; (2) **strategic narrative**; (3) **IC snapshot**. Industry structure and market-size content are on the prior Industry Overview slide — do not duplicate them.

Use `query_financial_data` and `calculate_financial_metrics` for the target’s LTM revenue, EBITDA, growth, and margins when available. Peer EV, market caps, and trading multiples must come from **provided materials only** unless the user enabled live market data; otherwise [NOT FOUND IN SOURCE]. Do not invent quotes or as-of dates.

Context: Tables and labeled bullets over long prose. No fluff.

Output structure: Markdown. Each section is a ### heading numbered below. Use **Label:** bullets where specified.

### 1. Regional and international comparables (Item 9)

Build **public / listed / named** peer sets **only from the documents**. Aim for **3–4 regional** peers (same geography or regulatory zone as the target when possible) and **3–4 international** peers (global leaders or same business model in tier-one markets). If fewer names exist, use what you have and state gaps.

State **as-of date** for any market or trading data **if** the materials give one.

**Regional peer set** — markdown table:

| Company | Region | EV ($M) | EV/EBITDA (LTM) | EV/EBITDA (NTM) if available | Revenue growth YoY | EBITDA margin |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |

Include a *Regional average* row only if averages are computable from sourced cells (otherwise omit).

**International peer set** — same columns. Include *International average* row only when computable.

**Target / this investment:** Add a final row or short table for implied or stated **EV**, **multiples**, **growth**, **margin** for the target using only document or tool outputs; [NOT FOUND IN SOURCE] for missing cells.

Emphasize **EV/EBITDA** and **EV/Revenue**; use **P/E** only if sector-appropriate and data exists.

Then:

- **Valuation gap:** How regional vs. international multiple levels compare in the materials (qualitative if numbers sparse).
- **Operational comparison:** Target growth and margin vs. peer set (Rule-of-40 only if applicable and sourced).
- **Multiple justification:** Whether the target’s entry or implied multiple looks **fair, rich, or cheap** vs. that evidence.
- **Peer benchmarking (headline):** One line — target multiple vs. regional average **if** computable.
- **Valuation support:** One line — multiples **supported vs. aggressive** given growth/margin/scarcity in the docs.

### 2. Strategic narrative

Exactly **three paragraphs** of plain prose (no bullets):

1. Competitive landscape and target positioning vs. peers.
2. Technological or secular shifts in value creation/capture.
3. **Alpha angle** for this deal.

### 3. IC snapshot

- **Industry thesis:** One sentence.
- **Alpha opportunity:** Per documents.
- **Key industry risk:** Per documents.
- **Comps takeaway:** Premium or discount vs. regional (or international) peers if §1 supports it; else [NOT FOUND IN SOURCE].

Formatting rules:

- Inline source hints where helpful.
- Tone: objective and direct.
- One **Sources** section at the end: plain text only (no ** bold in Sources).
"""

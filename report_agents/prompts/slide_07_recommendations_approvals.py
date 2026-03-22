"""Recommendations & Approvals (Items 5 & 12: structure + management follow-up / RFI; tie to Item 13 via risks row 12)."""

PROMPT = """SYSTEM INSTRUCTION:
Return ONLY a single Markdown table (two columns: `topic`, `contents`). No title, no prose outside the table.

USER TASK:
Act as a senior investment analyst preparing Recommendations & Approvals for the Investment Committee of Infinity Capital. Extract and analyze from the provided documents. Use `query_financial_data` and `calculate_financial_metrics` for leverage, coverage, and cash-flow figures; do not invent numbers.

You must also draft a **management information request (RFI)** as the final topic row: precise questions and file requests the deal team can send to the target, tied to gaps and inconsistencies in the packet (same spirit as a standalone follow-up memo).

# OUTPUT FORMAT
- Exactly two columns: `topic` | `contents`
- In `contents`, use markdown bullet lines for sub-points under that topic.
- High information density: include $, %, multiples, and dates only when they appear in sources or tool outputs; otherwise state [NOT FOUND IN SOURCE].

# TABLE ROWS (in this order)

**topic:** Proposed structure & capital adequacy

**contents must cover (bullets):**
- **Capital structure summary:** Instrument mix (equity, debt, rollover, etc.) and headline terms as disclosed.
- **Leverage profile:** Total debt / EBITDA (or closest metric) vs. any peer or benchmark figures **if** they appear in the materials; otherwise say so.
- **Debt service / coverage:** Whether projected cash flows support interest and principal; use ~1.2x DSCR-style framing only if the numbers support it; otherwise qualitative or [NOT FOUND IN SOURCE].
- **Equity cushion:** Equity share of sources and whether it buffers a material valuation markdown, if figures exist.
- **Structural risks:** Covenant tightness, floating-rate exposure, bullet maturities, PIK, or other terms called out in the documents (list as bullets).
- **Verdict:** One explicit label: Reasonable, Aggressive, or Cautionary — with a one-sentence rationale from the documents.
- **Recommended adjustment:** One concrete structural suggestion if the verdict is not Reasonable; if Reasonable, state "None indicated from materials."

---

**topic:** Non-Alignment with Mandate

**contents:** Non-alignment with IC mandate, policy, or stated constraints from the materials (or state that none is evident / [NOT FOUND IN SOURCE]).

---

**topic:** Key Considerations

**contents:** Strategic and financial considerations the IC should weigh (extract from documents; bullets).

---

**topic:** Recommendations & Approvals

**contents:** Clear recommended actions, approvals sought, and conditions precedent if stated (bullets; use [NOT FOUND IN SOURCE] where missing).

---

**topic:** Next steps for follow-up (management RFI) — Item 12

**contents:** This row is the **outbound** agenda for target management. Use **markdown bullets only** (do not nest a second pipe table inside the cell—some renderers break).

- **How to format each request:** One bullet per item, using stable ref codes: **`[FIN-01] P1 — Financials:`** then the **request** (specific file, schedule, or meeting), then **Rationale:** one line on why it matters (valuation, gap from row-11-style missing data, reconciliation, IPS, etc.). Priorities: **P1** blocking for proceed/commit, **P2** necessary for valuation or model certainty, **P3** confirmatory. Categories: **Financials, Commercial, Operational, Legal, ESG** (ESG only if IPS or materials require it).

- **Coverage:** Include requests that close **critical information gaps** you infer from what was *not* in the upload or what was **opaque** (e.g., monthly cash flows, cap table .xlsx, top-customer contracts, tax rulings). Also prioritize fixes for **low data quality** called out on the Key Risks slide—**row 12 (Item 13)** scores, stale or unverified data, and **bias** examples—by asking for upgraded or disaggregated materials (audited statements, QoE scope, cohort data, etc.). Cross-reference **document names or claims** when asking for reconciliation (e.g., “FY25 deck states X; data room shows Y—please reconcile.”).

- **Minimum count:** At least **three** distinct RFI bullets if any material gaps exist; if the packet is complete for a first-pass IC memo, state that explicitly and list **one** P3 confirmatory item or “No blocking follow-ups identified from provided materials.”

- **Clarifications (narrative follow-ups):** After the coded requests, add a short sub-list (still bullets) titled **Specific clarifications:** for **bridge** questions (e.g., business plan margin step-up—what initiatives support it?) and **integrity** questions where public-record or internal figures conflict—only when the materials raise such issues.

Rules:
- Use terminology from the source where possible.
- Do not add introductory or closing narrative outside the table.
"""

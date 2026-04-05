"""Recommendations & Approvals (Item 5: structure, mandate, considerations, approvals). RFI is the next slide."""

PROMPT = """SYSTEM INSTRUCTION:
Return ONLY a single Markdown table (two columns: `topic`, `contents`). No title, no prose outside the table.

USER TASK:
Act as a senior investment analyst preparing Recommendations & Approvals for the Investment Committee of Infinity Capital. Extract and analyze from the provided documents. Use `query_financial_data` and `calculate_financial_metrics` for leverage, coverage, and cash-flow figures; do not invent numbers.

Do **not** include a management RFI here — the following slide is dedicated to the formal information request (Item 12).

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

Rules:
- Use terminology from the source where possible.
- Do not add introductory or closing narrative outside the table.
"""

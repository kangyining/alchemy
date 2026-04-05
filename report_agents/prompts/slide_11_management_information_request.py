"""Management information request (RFI) — Item 12; ties to Key Risks row 11–12 and data quality."""

PROMPT = """
Role: Act as a senior M&A associate for Infinity Capital. Draft the **outbound** management information request (RFI): precise questions and concrete file asks the deal team can send to the target. Use `query_financial_data` and `calculate_financial_metrics` only where you need to anchor a request in a specific missing number.

Assume prior slides in the packet may cover recommendations, risks, and gaps; **do not** repeat the Recommendations & Approvals table — this slide is **only** the RFI.

Output structure: Markdown.

### 1. Formal information request list

| Ref # | Category | Inquiry | Priority | Rationale |
| :---- | :---- | :---- | :---- | :---- |

**Row rules:**
- **Ref #:** Stable codes: **FIN-**, **COM-**, **OPS-**, **LEG-**, **ESG-** (ESG only if IPS or materials require it) plus a two-digit sequence per category.
- **Category:** Financials, Commercial, Operational, Legal, or ESG as applicable.
- **Inquiry:** Specific deliverable (file, schedule, workshop) or precise question — not vague.
- **Priority:** **P1** blocking for proceed/commit, **P2** necessary for valuation or model certainty, **P3** confirmatory.
- **Rationale:** One phrase tying to valuation, reconciliation, IPS fit, or a **critical gap** / **opaque** disclosure from the materials.

**Coverage:** Include requests that close **critical information gaps** (what was *not* uploaded or is **opaque**). Prioritize follow-ups aligned with **low data quality** on the Key Risks slide — **row 11 (Item 11)** missing data and **row 12 (Item 13)** quality scores, stale or unverified data, and **bias** examples — by asking for upgraded or disaggregated materials (audited statements, QoE scope, cohort data, etc.). Cross-reference **document names or claims** when asking for reconciliation (e.g., “FY25 deck states X; data room shows Y—please reconcile.”).

**Minimum count:** At least **three** distinct rows if any material gaps exist. If the packet is complete for a first-pass IC memo, state that in one sentence under the table and add **one** P3 confirmatory row or a row that says no blocking follow-ups from provided materials.

### 2. Specific clarifications

Bullet list (plain lines starting with dash). Title the block **Specific clarifications:** — **bridge** questions (e.g., plan margin step-up—what initiatives support it?) and **integrity** questions where public-record or internal figures conflict, **only** when the materials raise such issues. If none, one bullet: “No additional clarification topics identified from provided materials.”

Formatting:
- Tone: professional, outcome-oriented.
- Sources section at end: plain text, no ** bold in Sources.
"""

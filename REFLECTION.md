# Suraksha — Written Reflection

*Assignment Section I, 200–300 words. This is a working draft with the real,
verified details filled in — read it once and put it in your own voice
before submitting.*

---

**1. My new output validation check.** It is called `citations_are_grounded`.
Every `(Source: …)` an answer cites must actually be one of the sources
retrieved for that request. Without it, the "plausible-sounding but
never-retrieved" citation reaches the user: for example, an answer to the
breach-notification question citing `02_incident_response_plan.docx` when
retrieval only returned the Access Control Policy. The answer is
non-empty, well-formed, PII-free, and injection-free — Pramaan's original
four checks all pass — so a user acting on security policy would trust a
citation that cannot be reproduced from the request's own context. The
deliberate test case (`99_ghost_policy.pdf` / a ghost `.docx`) fails the
check and returns the fallback instead; the same answer passes once the
cited document really was retrieved.

**2. The component that matters most here.** For a security-policy
assistant, I would pick the **audit log**, because this is the one domain
where "why did the system say that?" must survive an audit months later.
Policy answers drive access decisions and incident responses; the audit
row is the only artefact that can justify a past answer without
re-running a probabilistic pipeline. Injection defence and the refusal
guardrail reduce bad answers, but the log is what makes every answer
accountable.

**3. The one Partial item.** Checklist item 2.3 — confidence thresholds.
Suraksha inherits Pramaan's starting values (High ≥ 0.5, Medium ≥ 0.3)
without tuning them against this corpus. Closing the gap means collecting
the live relevance scores for the five domain questions, confirming each
lands in the intended band (and that the out-of-scope question refuses),
then either adjusting the constants or documenting evidence that the
defaults are right for this embedding model and these documents.

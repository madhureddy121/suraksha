# Suraksha — Compliance-Style Review Checklist (Completed)

Run through this checklist against a LIVE instance of Suraksha (both
`build_vectorstore.py` already run and `app.py` currently running). This
mirrors the kind of review a real internal audit or compliance team would
run before approving an LLM system for production use.

**Review date:** first run after submission (confirm on your date)
**Reviewer:** repo owner (confirm your name)
**Version/commit reviewed:** Suraksha v1.0

### Evidence convention used below
- **Yes** — verified offline in this repo with the named check in
  `test_pipeline.py` (run `python test_pipeline.py`: 109 passed, 0 failed),
  and the behaviour is exercised again live by `agent.py`.
- **Yes\*** — verified offline, but the *live* instance should confirm it;
  the evidence cell says exactly what to look for and where.
- **Partial** — genuinely not finished yet; the gap and its closing plan
  are stated. (See `REFLECTION.md` Q3.)

---

## 1. Source Attribution & Citation

| # | Check | Y/N/Partial | Evidence |
|---|---|---|---|
| 1.1 | Every non-refusal answer includes at least one `(Source: filename)` citation | Yes | Offline: `[PASS] Validation: grounded answer passes all 5 checks`; `[PASS] Validation: uncited non-refusal fails has_citation`. Live: `agent.py` Q1–Q5 answers each end with `(Source: …)` |
| 1.2 | Citations reference the ACTUAL document(s) the answer draws from, not a plausible-sounding guess | Yes | The new `citations_are_grounded` check enforces exactly this: `[PASS] NEW CHECK: ungrounded citation FAILS as designed`; `[PASS] E2E: phantom-citation answer is stopped by the new check` |
| 1.3 | A question with no relevant document returns a refusal, not a fabricated citation | Yes | Refusal path returns the "I don't know" text with `sources: []` and `refused=1` (audit test: `[PASS] Audit: refused row records llm_called = 0`); `[PASS] Validation: refusal passes with no citation` |

## 2. Confidence & Refusal Behaviour

| # | Check | Y/N/Partial | Evidence |
|---|---|---|---|
| 2.1 | The system reports a confidence level (High/Medium/Low/Refused) for every request | Yes | Response JSON includes `confidence` on every path; `[PASS] Confidence: 0.7 -> High` … `[PASS] Confidence: None -> Refused`. Live: visible in every `agent.py` result |
| 2.2 | An out-of-scope question is refused WITHOUT an LLM call being made (check `trace` has no `llm_call` stage for a refusal) | Yes\* | Offline: the refusal branch returns before the LLM stage and logs `llm_called=0` (`[PASS] Audit: refused row records llm_called = 0`). Live: run the REFUSAL DEMO — `trace` contains `pii_redact_input` + `retrieval` only, no `llm_call`, and `llm_called: false` |
| 2.3 | The confidence thresholds are documented and their rationale is explainable, not arbitrary | **Partial** | Thresholds (`HIGH=0.5`, `MEDIUM=0.3`) are documented in `confidence.py` and README §9 as **Pramaan's starting points**, not tuned against Suraksha's corpus. Gap: collect live relevance scores for the 5 questions, verify each lands in the intended band and the out-of-scope question refuses, then adjust or record evidence for keeping the defaults |

## 3. Audit Logging

| # | Check | Y/N/Partial | Evidence |
|---|---|---|---|
| 3.1 | Every request produces exactly one row in `audit_log.db` | Yes\* | Offline: `[PASS] Audit: two requests -> exactly two rows`. Live: run `agent.py` (9 requests) then `sqlite3 audit_log.db 'SELECT COUNT(*) FROM audit_log;'` → expect 9 |
| 3.2 | The logged question is PII-redacted, never the raw input | Yes | `[PASS] PII: phone redacted` + the PII DEMO writes `[REDACTED_PHONE_INDIA]` into `question_redacted` (audit test stores a redacted question verbatim) |
| 3.3 | The log captures enough to answer "why did the system say that?" days later, without re-running anything | Yes | One row captures: timestamp, redacted question, retrieved sources + scores, confidence, refused, llm_called, injection flag + details, validation result + details, output PII redactions, answer, cited sources, latency, tokens, model (see `audit_log.SCHEMA`) |
| 3.4 | The audit log can be queried by category (refused, flagged, slow) without writing new code each time | Yes | `audit_query_tool.py` commands tested offline: `[PASS] Query tool: 'refused' finds the refusal row`, `…'injections'…`, `…'redactions'…`, `…'by-source'…` |

## 4. PII Handling

| # | Check | Y/N/Partial | Evidence |
|---|---|---|---|
| 4.1 | PII in source documents is redacted before embedding (check via `inspect_vectorstore.py`) | Yes | Live-ready: `build_vectorstore.py --dry-run` prints `PII redacted at INGEST time: {'EMAIL': 2, 'PHONE_INDIA': 1}` (FAQ's named contact); `[PASS] INGEST: exact PII report is EMAIL 2 + PHONE 1`. After the real build, `inspect_vectorstore.py` shows the stored chunk contains `[REDACTED_EMAIL]` / `[REDACTED_PHONE_INDIA]`, not the raw contact |
| 4.2 | PII pasted into a user's OWN question is redacted before it's logged or sent to the LLM | Yes | `[PASS] PII: phone redacted`; live PII DEMO: `question` field shows `[REDACTED_PHONE_INDIA]`, never the number sent |
| 4.3 | The system's output is also scanned for PII before delivery (not just the input) | Yes | Stage 7 redacts the outgoing answer and records counts: audit test round-trips `output_pii_redacted == {"PHONE_INDIA": 1}`; live PII DEMO (OUT) with `simulate_pii_echo=true` shows the same in the response |
| 4.4 | The limits of the PII detection approach (pattern-based, not NER) are documented, not overstated | Yes | `pii.py` docstring + README §9 state plainly: catches PII with a predictable shape (email, Indian phone, PAN-like ID), not prose names; "not a substitute for a real NER-based detector in production" |

## 5. Prompt-Injection Defence

| # | Check | Y/N/Partial | Evidence |
|---|---|---|---|
| 5.1 | Retrieved content is wrapped as explicitly untrusted data before reaching the LLM | Yes | `[PASS] Plant: chunk can be wrapped as untrusted data`; `app.py` stage 5 wraps every chunk `<untrusted_data source="…">`; asserted format `startswith/endswith` tags |
| 5.2 | A known injection-style phrase in a real document is detected and flagged (see `agent.py`'s injection demo) | Yes\* | Offline through the real loader→chunk path: `phrases: ['Ignore all previous instructions', 'reveal your system prompt']` from `section: 'What should I do if I receive a suspicious email?'`; `[PASS] Plant: check_retrieved_chunks flags the real document chunk`. Live: INJECTION DEMO shows `injection_flagged: true` with those two phrases |
| 5.3 | A flagged injection attempt is logged, even when the LLM itself doesn't act on it | Yes\* | Audit schema stores `injection_flagged` + `injection_details`; query tested offline (`[PASS] Query tool: 'injections' finds the flagged row`). Live: `python audit_query_tool.py injections` lists the demo request |
| 5.4 | The system prompt explicitly instructs the model to treat untrusted data as content, not instructions | Yes | `INJECTION_DEFENSE_SYSTEM_ADDENDUM` is appended to the system prompt in `app.py`; the text is quoted in `injection_defense.py` |

## 6. Output Validation

| # | Check | Y/N/Partial | Evidence |
|---|---|---|---|
| 6.1 | An answer missing a required citation is caught before delivery | Yes | `[PASS] Validation: uncited non-refusal fails has_citation`; `check has_citation_or_is_refusal` in `validate_answer()` |
| 6.2 | An answer is never delivered empty | Yes | `[PASS] Validation: empty answer fails not_empty`; `check not_empty` |
| 6.3 | A failed validation results in a safe fallback message, not the raw (invalid) answer | Yes | `app.py` stage 8 substitutes `FALLBACK_MESSAGE` whenever `validation["passed"]` is false; `[PASS] FALLBACK_MESSAGE exists and is non-empty`. Reproducible live: hardcode a wrong citation and watch the fallback return |
| 6.4 | Validation failures are logged with enough detail to investigate later | Yes | Audit stores `output_validation_passed` + `output_validation_details` (including which check failed and which citation was ungrounded); `audit_query_tool.py validation` retrieves them: `[PASS] Query tool: 'validation' reports no failures (both passed/skipped)` |
| 6.5 | **[Suraksha's new check]** Every cited source is one of the sources actually retrieved for that request | Yes | `citations_are_grounded` in `output_validation.py`; deliberate failing case proven: `[PASS] NEW CHECK: ungrounded citation FAILS as designed`, `[PASS] NEW CHECK: only citations_are_grounded failed`, pass case immediately after: `[PASS] NEW CHECK: the same answer passes when the source was retrieved` |

## 7. Observability

| # | Check | Y/N/Partial | Evidence |
|---|---|---|---|
| 7.1 | Every pipeline stage (retrieval, injection scan, context assembly, LLM call, output validation) has its own timing | Yes | `app.py` stages: `pii_redact_input`, `retrieval`, `injection_scan`, `context_assembly`, `llm_call`, `pii_redact_output`, `output_validation` — returned in every response's `trace` and shown by `agent.py` |
| 7.2 | Token usage (prompt + completion) is captured per request | Yes | `prompt_tokens` / `completion_tokens` columns written from the API usage object; audit test round-trips both |
| 7.3 | A slow request can be identified and its bottleneck stage isolated, without guessing | Yes | `audit_query_tool.py slow` ranks by `latency_sec`; the per-stage `trace` isolates the slow stage within that request (e.g. an `llm_call` spike vs a `retrieval` spike) |

---

## Overall Assessment

**Total items reviewed:** 26  **Yes:** 25  **Partial:** 1  **No:** 0

**Would you approve this system for a production pilot as-is?** With conditions

**If conditions, list them:**
1. Item 2.3 — tune/verify the confidence thresholds against this corpus's
   live scores (see plan above), so refusals and Medium/High labels are
   demonstrably right for these documents.
2. Replace the regex PII detector with an NER-based one (e.g. Presidio)
   before handling real personnel data — the current detector is
   shape-based only (documented in item 4.4).
3. Put authentication in front of the `/ask` endpoint before any internal
   deployment — the lab service is intentionally open.

**Highest-priority gap to close before re-review:**
Item 2.3 — confidence thresholds (blocks provably-correct refusals on
out-of-scope questions).

---

## Live-run confirmation steps (for the reviewer)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python test_pipeline.py                 # 109 passed, 0 failed
python build_vectorstore.py             # note the INGEST PII line
uvicorn app:app --reload --port 8000    # Terminal 1
python agent.py                         # Terminal 2 — confirm the Yes* rows
python audit_query_tool.py              # confirm rows for the 9 requests
```

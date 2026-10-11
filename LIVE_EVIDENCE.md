# Suraksha — Live Evidence (paste your first-run output here)

The offline suite (`test_pipeline.py`, 109 checks) already proves the
*same logic* these items exercise. After your first live run with a real
API key, paste/confirm the lines below — these are the exact items the
assignment asks a reviewer to see. Replace each `...` placeholder.

## 1. Build output (`python build_vectorstore.py`)

```
Total chunks to embed: ...
PII redacted at INGEST time: ...
```

Expected ingest PII: `{'EMAIL': 2, 'PHONE_INDIA': 1}` (the FAQ's named
Security Operations contact).

## 2. INJECTION DEMO — planted phrase detected end-to-end (`python agent.py`)

```
injection_flagged: ...
injection_details: ...
```

Expected phrases in the details:
`'Ignore all previous instructions'` and `'reveal your system prompt'`,
source `03_security_awareness_faq.html` — with a normal, safe answer.

## 3. PII DEMO (IN) — question redaction

```
Question (as logged): ...
```

Expected: `[REDACTED_PHONE_INDIA]` where the phone number was sent.

## 4. PII DEMO (OUT) — outgoing answer redaction

```
Output PII redacted: ...
```

Expected: `{'PHONE_INDIA': 1}` and the answer ending in
`[REDACTED_PHONE_INDIA]`.

## 5. REFUSAL DEMO — no LLM call

```
Confidence: ...
LLM called: ...
Trace (per-stage sec): ...
```

Expected: `Refused`, `LLM called: False`, and **no `llm_call` stage** in
the trace.

## 6. Audit log (`python audit_query_tool.py`)

```
(paste the confidence breakdown, refused, injections, redactions and
 latency sections here)
```

Expected: 9 total requests after one full `agent.py` run; exactly 1
refused; at least 1 injection-flagged; at least 1 output-redaction row.

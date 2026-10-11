"""
pii.py

Suraksha — PII Detection & Redaction (Ingest AND Serving Time)
==================================================================
Same three-point pattern as Pramaan, now guarding IT Security Policy
content. PII can enter or leave the pipeline in more than one place:

  1. INGEST TIME  (build_vectorstore.py) — redact PII in source documents
     before they're chunked and embedded. In this repo the Security
     Awareness FAQ deliberately contains a named Security Operations
     contact (email + phone) so this stage has something real to catch.
  2. SERVING TIME, on the way IN (app.py) — a user might paste PII into
     their own question ("my number is 98765..., is my incident still
     open?"). That should never reach the LLM or the audit log raw.
  3. SERVING TIME, on the way OUT (app.py) — even with clean inputs, a
     model can occasionally echo back something PII-shaped from its
     context. The answer is redacted before delivery, as a last line of
     defence.

This is intentionally still a simple, regex-based approach — not a
substitute for a real NER-based PII detector in production. It catches
PII with a predictable SHAPE (an email always has an @), not PII
expressed as plain prose (a name).
"""
import re

PATTERNS = {
    "EMAIL": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "PHONE_INDIA": re.compile(r"(?:\+91[-\s]?)?[6-9]\d{9}\b"),
    "PAN_LIKE_ID": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
}


def redact_pii(text: str) -> tuple[str, dict]:
    """Replace any matched PII with a labelled placeholder.
    Returns the redacted text AND a count of what was redacted, so callers
    can report what happened without ever printing the actual PII."""
    redaction_counts = {}
    redacted_text = text
    for label, pattern in PATTERNS.items():
        matches = pattern.findall(redacted_text)
        if matches:
            redaction_counts[label] = len(matches)
            redacted_text = pattern.sub(f"[REDACTED_{label}]", redacted_text)
    return redacted_text, redaction_counts


def contains_pii(text: str) -> bool:
    """Quick boolean check, used where callers just need to know WHETHER
    to flag something, without needing the full redacted text back."""
    return any(pattern.search(text) for pattern in PATTERNS.values())

"""
output_validation.py

Suraksha — Output Validation: Schema Checks & Content Filters Before Delivery
=================================================================================
Everything so far has focused on controlling what goes INTO the LLM.
This module checks what comes OUT, before it's ever returned to a user —
the last line of defence, catching problems that slipped past every
earlier stage.

FIVE checks, all fast and deterministic (no extra LLM call needed):

  1. Not empty — an answer must actually contain something.
  2. Citation present — if the answer isn't a refusal, it must contain at
     least one (Source: ...) citation, per the system prompt's own rule.
  3. No leaked PII — re-run the SAME PII patterns from pii.py against the
     OUTPUT, not just the input. A model can occasionally echo something
     PII-shaped back from its context.
  4. No unresolved injection phrasing — if the answer itself contains a
     phrase from injection_defense.py's suspicious pattern list, that's a
     strong signal something upstream didn't hold.
  5. [SURAKSHA'S NEW CHECK] Citations are grounded — every source cited in
     the answer must actually be one of the sources that were retrieved for
     THIS request. Catches the "plausible-sounding but never-retrieved"
     citation: an answer that invents (Source: 02_incident_response_plan.docx)
     when that document wasn't in the retrieved context at all. Checks 1-4
     cannot catch this — a fabricated citation is non-empty, perfectly
     well-formed, contains no PII, and contains no injection phrasing. See
     README for the deliberate failing/passing test case.

If any check fails, app.py does NOT deliver the generated answer — it
substitutes a safe fallback message and logs the validation failure.
"""
import re

from pii import contains_pii
from injection_defense import scan_for_injection

CITATION_PATTERN = re.compile(r"\(Source:\s*([^)]+)\)", re.IGNORECASE)

REFUSAL_MARKERS = ["i don't know", "cannot", "not able to", "no relevant"]

# Page/section references that can legitimately follow a filename inside a
# citation, e.g. "(Source: 01_access_control_policy.pdf, p. 2)".
_PAGE_REF_PATTERN = re.compile(
    r"^(p\.?|page|pages|para\.?|paragraph|section|sec\.?|clause|appendix|annex)\s*\d+[a-z]?$",
    re.IGNORECASE,
)


def is_refusal(answer: str) -> bool:
    lower = answer.lower()
    return any(marker in lower for marker in REFUSAL_MARKERS)


def extract_cited_sources(answer: str) -> list[str]:
    """Pulls out the source names an answer actually cites:
    '(Source: 01_access_control_policy.pdf)' -> ['01_access_control_policy.pdf']"""
    return [match.group(1).strip() for match in CITATION_PATTERN.finditer(answer)]


def _normalise(text: str) -> str:
    return " ".join(text.lower().replace("_", " ").replace("-", " ").split())


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _is_grounded(cited: str, retrieved_sources: list[str]) -> bool:
    """A citation is grounded if it plausibly refers to one of the sources
    that were actually retrieved for this request. Two rules are accepted:

      1. Filename containment — the cited string contains a retrieved
         filename (or vice versa), which also covers suffixes such as
         ', p. 2' after the filename.
      2. Token subset — every word in the citation appears in the same
         retrieved filename, which covers title-style citations such as
         'Access Control Policy' for '01_access_control_policy.pdf'.
    """
    cited_norm = _normalise(cited)
    cited_tokens = _tokens(cited)
    if not cited_tokens:
        return False
    for source in retrieved_sources:
        source_norm = _normalise(source)
        if not source_norm:
            continue
        if cited_norm == source_norm or cited_norm in source_norm or source_norm in cited_norm:
            return True
        if cited_tokens <= _tokens(source):
            return True
    return False


def _citation_grounding_report(answer: str, retrieved_sources: list[str]):
    """Returns (grounded: bool, ungrounded_fragments: list[str])."""
    fragments = []
    for citation in extract_cited_sources(answer):
        for fragment in re.split(r"[,;]", citation):
            fragment = fragment.strip().strip("'\"")
            if not fragment or _PAGE_REF_PATTERN.match(fragment):
                continue
            fragments.append(fragment)

    if not fragments:
        # No citations to verify — either a refusal, or check 2 will fail
        # the answer for having no citation at all.
        return True, []

    ungrounded = [f for f in fragments if not _is_grounded(f, retrieved_sources)]
    return len(ungrounded) == 0, ungrounded


def validate_answer(answer: str, retrieved_sources: list | None = None) -> dict:
    """Runs all five checks and returns a report:
    {"passed": bool, "checks": {...}, "details": str}
    `passed` is True only if every applicable check passes.

    `retrieved_sources` is the list of source filenames that were actually
    retrieved for this request (app.py always passes it). When it is None,
    the fifth check is skipped and recorded as passed with a note, so this
    function can still be called in contexts without retrieval results."""
    checks = {}
    ungrounded: list[str] = []

    checks["not_empty"] = bool(answer and answer.strip())

    refusal = is_refusal(answer)
    checks["has_citation_or_is_refusal"] = refusal or bool(CITATION_PATTERN.search(answer))

    checks["no_leaked_pii"] = not contains_pii(answer)

    injection_phrases = scan_for_injection(answer)
    checks["no_injection_phrasing"] = len(injection_phrases) == 0

    # ---- Suraksha's new check: citation provenance ----
    if retrieved_sources is None:
        checks["citations_are_grounded"] = True
    else:
        grounded, ungrounded = _citation_grounding_report(answer, retrieved_sources)
        checks["citations_are_grounded"] = grounded

    passed = all(checks.values())

    failed_checks = [name for name, ok in checks.items() if not ok]
    parts = ["All checks passed." if passed else f"Failed: {', '.join(failed_checks)}"]
    if injection_phrases:
        parts.append(f"suspicious phrases in answer: {injection_phrases}")
    if ungrounded:
        parts.append(f"ungrounded citations (not retrieved for this request): {ungrounded}")
    if retrieved_sources is None:
        parts.append("citations_are_grounded check skipped (no retrieved-sources list provided).")

    return {"passed": passed, "checks": checks, "details": " ".join(parts)}


FALLBACK_MESSAGE = (
    "I'm not able to deliver a response to this question right now — it "
    "did not pass an internal safety check. Please rephrase your question "
    "or contact support if this persists."
)

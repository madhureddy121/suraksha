"""
confidence.py

Suraksha — Confidence Indicators & Refusal Patterns
=======================================================
Turns a raw retrieval relevance score into a human-readable confidence
LEVEL, and makes the refusal decision explicit and testable — rather
than a single hardcoded number buried inside app.py.

A weather forecaster doesn't just say "70% chance of rain" and stop —
they also tell you what that number means for whether to carry an
umbrella. This module is that translation step for Suraksha's retrieval
scores.
"""

# Tune these for your embedding model and documents — see README.
HIGH_THRESHOLD = 0.5
MEDIUM_THRESHOLD = 0.3


def confidence_level(best_score) -> str:
    """Translates a raw relevance score into a level a human (or an audit
    log) can act on without needing to know what a 'relevance score' is."""
    if best_score is None:
        return "Refused"
    if best_score >= HIGH_THRESHOLD:
        return "High"
    if best_score >= MEDIUM_THRESHOLD:
        return "Medium"
    return "Low"


def should_refuse(best_score) -> bool:
    """The actual refusal decision. Kept separate from confidence_level()
    so the THRESHOLD for refusing can be tuned independently of how
    confidence is DISPLAYED."""
    return best_score is None or best_score < MEDIUM_THRESHOLD


def best_score_from_results(results: list) -> float:
    """results: list of (doc, score) pairs. Returns the highest score, or
    None if the list is empty."""
    scores = [score for _, score in results if score is not None]
    return max(scores) if scores else None

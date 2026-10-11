"""
context.py

Suraksha — Context Assembly: Evidence Packing & Deduplication
==================================================================
Carried over unchanged from Pramaan. Deduplicates near-identical
retrieved chunks, then packs whatever remains into a fixed character
budget before the LLM ever sees it.
"""


def normalise(text: str) -> str:
    return " ".join(text.lower().split())


def deduplicate(results: list) -> list:
    seen_normalised = []
    deduped = []
    for doc, score in results:
        norm = normalise(doc.page_content)
        is_duplicate = any(norm in seen or seen in norm for seen in seen_normalised)
        if not is_duplicate:
            seen_normalised.append(norm)
            deduped.append((doc, score))
    return deduped


def pack_context(results: list, max_chars: int = 3000) -> str:
    pieces = []
    total_chars = 0
    for doc, score in results:
        source = doc.metadata.get("source", "unknown")
        piece = f"(From {source})\n{doc.page_content}"
        if total_chars + len(piece) > max_chars:
            break
        pieces.append(piece)
        total_chars += len(piece)
    return "\n\n---\n\n".join(pieces)


def assemble_context(results: list, max_chars: int = 3000):
    deduped = deduplicate(results)
    context_text = pack_context(deduped, max_chars=max_chars)
    return context_text, deduped

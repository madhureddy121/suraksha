"""
chunking.py

Suraksha — Chunking (carried over from Pramaan / Disha)
==========================================================
Suraksha is about the trust layer AROUND retrieval and generation, not
about chunking itself — so we fix on one solid strategy (overlap) and
move on.
"""


def overlap_chunk(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return [c.strip() for c in chunks if c.strip()]


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    return overlap_chunk(text, chunk_size=chunk_size, overlap=overlap)

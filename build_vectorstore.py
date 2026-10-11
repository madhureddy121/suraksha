"""
build_vectorstore.py

Suraksha — Build the Knowledge Base (Step 1 of 3)
=====================================================
Same ingest -> chunk -> embed -> index flow as Pramaan. PII redaction at
ingest time happens here — the Security Awareness FAQ's named contact
(email + phone) gets scrubbed before any chunk is embedded. Suraksha's
other two PII points (the incoming question and the outgoing answer) live
in app.py, not here.

Run:
    python build_vectorstore.py                # full build (needs an API key)
    python build_vectorstore.py --dry-run      # load + redact + chunk only, no API key needed
"""
import glob
import os
import shutil
import sys

from dotenv import load_dotenv
from langchain_core.documents import Document

from loaders import load_document
from chunking import chunk_text
from pii import redact_pii

load_dotenv()

EMBED_MODEL = "text-embedding-3-small"
COLLECTION_NAME = "suraksha_documents"
PERSIST_DIR = "./chroma_store"


def build(dry_run: bool = False):
    print("=" * 64)
    print("Suraksha — Building the Knowledge Base" + (" (DRY RUN)" if dry_run else ""))
    print("=" * 64)

    filepaths = sorted(glob.glob("documents/*"))
    if not filepaths:
        print("No documents found in documents/ — nothing to build.")
        return

    print(f"\nFound {len(filepaths)} source document(s):")
    for f in filepaths:
        print(f"  - {os.path.basename(f)}")

    all_documents = []
    total_pii_redactions = {}

    for filepath in filepaths:
        filename = os.path.basename(filepath)
        print(f"\nProcessing {filename} ...")

        raw_units = load_document(filepath)
        print(f"  Loaded as {len(raw_units)} source unit(s)")

        file_chunk_count = 0
        for unit in raw_units:
            redacted_text, pii_counts = redact_pii(unit["text"])
            for label, count in pii_counts.items():
                total_pii_redactions[label] = total_pii_redactions.get(label, 0) + count

            chunks = chunk_text(redacted_text)
            for i, chunk in enumerate(chunks):
                metadata = dict(unit["metadata"])
                metadata["chunk_index"] = i
                all_documents.append(Document(page_content=chunk, metadata=metadata))
                file_chunk_count += 1

        print(f"  -> {file_chunk_count} chunk(s) from this file")

    print(f"\nTotal chunks to embed: {len(all_documents)}")
    if total_pii_redactions:
        print(f"PII redacted at INGEST time: {total_pii_redactions}")
    else:
        print("No PII patterns matched during ingestion.")

    if dry_run:
        print("\nDry run complete — skipping embedding and storage (no API key needed).")
        return

    print("\nEmbedding and storing in ChromaDB...")
    from langchain_openai import OpenAIEmbeddings
    from langchain_chroma import Chroma

    embeddings = OpenAIEmbeddings(model=EMBED_MODEL)

    if os.path.exists(PERSIST_DIR):
        shutil.rmtree(PERSIST_DIR)

    Chroma.from_documents(
        documents=all_documents,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=PERSIST_DIR,
    )

    print("\n" + "=" * 64)
    print(f"Done. {len(all_documents)} chunks stored in {PERSIST_DIR}")
    print("Next step: start app.py (see README.md)")
    print("=" * 64)


if __name__ == "__main__":
    build(dry_run="--dry-run" in sys.argv)

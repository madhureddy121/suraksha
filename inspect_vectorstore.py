"""
inspect_vectorstore.py

Suraksha — Peek Inside the Vector Store
==========================================
Demystify what build_vectorstore.py actually created in ./chroma_store,
using the ChromaDB API and then plain SQLite directly.

Run this AFTER build_vectorstore.py:
    python inspect_vectorstore.py
"""
import sqlite3
import chromadb

print("=" * 64)
print("PART 1 — Through the ChromaDB API")
print("=" * 64)

client = chromadb.PersistentClient(path="./chroma_store")
collection = client.get_collection("suraksha_documents")

print(f"\nCollection name : {collection.name}")
print(f"Total chunks    : {collection.count()}")

print("\nA sample of 3 stored chunks, with their metadata:")
sample = collection.peek(limit=3)
for i, (doc, meta) in enumerate(zip(sample["documents"], sample["metadatas"]), start=1):
    print(f"\n  --- Chunk {i} ---")
    print(f"  metadata : {meta}")
    print(f"  text     : {doc[:100]}...")

print("\n" + "=" * 64)
print("PART 2 — Directly inside chroma.sqlite3")
print("=" * 64)

db_path = "./chroma_store/chroma.sqlite3"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]

print(f"\nReal tables found inside {db_path}:")
for t in tables:
    print(f"  - {t}")

conn.close()

print("\n" + "=" * 64)
print("A separate database: audit_log.db")
print("=" * 64)
print("""
Note that ./chroma_store/chroma.sqlite3 and ./audit_log.db are two
DIFFERENT SQLite databases, serving two different purposes:

  chroma.sqlite3  -- stores WHAT Suraksha knows (chunk text + metadata)
  audit_log.db    -- stores WHAT Suraksha has been ASKED and ANSWERED

Use audit_query_tool.py to inspect audit_log.db — this script only
looks at the knowledge base.
""")

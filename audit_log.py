"""
audit_log.py

Suraksha — Audit Logging: What to Log, How to Store, How to Query
======================================================================
WHAT to log, per request: a timestamp, the (PII-redacted) question, which
sources were retrieved and with what scores, the confidence level, whether
the pipeline refused, whether the LLM was called at all, whether an
injection attempt was flagged, whether output validation passed, the final
answer, which sources were actually cited, what PII was redacted from the
OUTGOING answer, latency, and token usage. Enough to reconstruct and
justify every answer Suraksha ever gave, without storing anything that
shouldn't be stored (raw PII never reaches this log — it's redacted before
logging, not after).

HOW to store: a real SQLite database (audit_log.db), one row per request,
in a single table with typed columns — queryable with plain SQL, not just
a growing text file no one can search.

HOW to query: see audit_query_tool.py for a runnable CLI with example
queries (refused requests, injection flags, validation failures, output
redactions, slow requests, requests citing a specific document, etc.).
"""
import sqlite3
import json
import time
from datetime import datetime, timezone

DB_PATH = "./audit_log.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    question_redacted TEXT NOT NULL,
    retrieved_sources TEXT,
    retrieved_scores TEXT,
    confidence_level TEXT,
    refused INTEGER NOT NULL,
    llm_called INTEGER NOT NULL,
    injection_flagged INTEGER NOT NULL,
    injection_details TEXT,
    output_validation_passed INTEGER,
    output_validation_details TEXT,
    output_pii_redacted TEXT,
    answer TEXT,
    cited_sources TEXT,
    latency_sec REAL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    model TEXT
);
"""


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(SCHEMA)
    return conn


def log_request(
    question_redacted: str,
    retrieved_sources: list,
    retrieved_scores: list,
    confidence_level: str,
    refused: bool,
    llm_called: bool,
    injection_flagged: bool,
    injection_details: str,
    output_validation_passed,
    output_validation_details: str,
    output_pii_redacted: dict,
    answer: str,
    cited_sources: list,
    latency_sec: float,
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
):
    """Write one audit row. Called once per /ask request, at the very end,
    after every other trust-stack stage has already run — so the log
    reflects the FULL outcome, not a partial one."""
    conn = _connect()
    conn.execute(
        """INSERT INTO audit_log (
            timestamp, question_redacted, retrieved_sources, retrieved_scores,
            confidence_level, refused, llm_called, injection_flagged,
            injection_details, output_validation_passed,
            output_validation_details, output_pii_redacted, answer,
            cited_sources, latency_sec, prompt_tokens, completion_tokens, model
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.now(timezone.utc).isoformat(),
            question_redacted,
            json.dumps(retrieved_sources),
            json.dumps(retrieved_scores),
            confidence_level,
            int(refused),
            int(llm_called),
            int(injection_flagged),
            injection_details,
            None if output_validation_passed is None else int(output_validation_passed),
            output_validation_details,
            json.dumps(output_pii_redacted or {}),
            answer,
            json.dumps(cited_sources),
            latency_sec,
            prompt_tokens,
            completion_tokens,
            model,
        ),
    )
    conn.commit()
    conn.close()


class Timer:
    """A tiny context manager for measuring latency around a block of
    code, used by app.py to time the whole request for the audit log."""
    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        self.elapsed = time.time() - self.start

"""
audit_query_tool.py

Suraksha — Querying the Audit Log
=====================================
A small CLI demonstrating the "how to query" half of audit logging —
plain SQL against a real SQLite file, no special tooling required.

Run AFTER agent.py has generated some activity to log:
    python audit_query_tool.py                  -> runs all example queries
    python audit_query_tool.py refused           -> just the refused requests
    python audit_query_tool.py injections        -> just the flagged injection attempts
    python audit_query_tool.py validation        -> just the validation failures
    python audit_query_tool.py redactions        -> requests where output PII was redacted
    python audit_query_tool.py slow              -> the 5 slowest requests
    python audit_query_tool.py by-source <file>  -> requests that cited a given source
"""
import sys

from audit_log import DB_PATH, _connect


def print_rows(cursor, columns):
    rows = cursor.fetchall()
    if not rows:
        print("  (no matching rows)")
        return
    for row in rows:
        print("  " + " | ".join(f"{col}={val}" for col, val in zip(columns, row)))


def query_refused():
    print("\n--- Refused requests (low confidence, no LLM call made) ---")
    conn = _connect()
    cursor = conn.execute(
        "SELECT timestamp, question_redacted, llm_called FROM audit_log "
        "WHERE refused = 1 ORDER BY timestamp DESC"
    )
    print_rows(cursor, ["timestamp", "question", "llm_called"])
    conn.close()


def query_injections():
    print("\n--- Requests where an injection attempt was flagged ---")
    conn = _connect()
    cursor = conn.execute(
        "SELECT timestamp, question_redacted, injection_details FROM audit_log "
        "WHERE injection_flagged = 1 ORDER BY timestamp DESC"
    )
    print_rows(cursor, ["timestamp", "question", "details"])
    conn.close()


def query_validation_failures():
    print("\n--- Requests where output validation FAILED (fallback message returned) ---")
    conn = _connect()
    cursor = conn.execute(
        "SELECT timestamp, question_redacted, output_validation_details FROM audit_log "
        "WHERE output_validation_passed = 0 ORDER BY timestamp DESC"
    )
    print_rows(cursor, ["timestamp", "question", "details"])
    conn.close()


def query_output_redactions():
    print("\n--- Requests where PII was redacted from the OUTGOING answer ---")
    conn = _connect()
    cursor = conn.execute(
        "SELECT timestamp, question_redacted, output_pii_redacted FROM audit_log "
        "WHERE output_pii_redacted IS NOT NULL AND output_pii_redacted != '{}' "
        "ORDER BY timestamp DESC"
    )
    print_rows(cursor, ["timestamp", "question", "output_pii_redacted"])
    conn.close()


def query_slow(limit: int = 5):
    print(f"\n--- {limit} slowest requests ---")
    conn = _connect()
    cursor = conn.execute(
        "SELECT timestamp, question_redacted, latency_sec FROM audit_log "
        "ORDER BY latency_sec DESC LIMIT ?", (limit,)
    )
    print_rows(cursor, ["timestamp", "question", "latency_sec"])
    conn.close()


def query_by_source(source_filename: str):
    print(f"\n--- Requests that cited source: {source_filename} ---")
    conn = _connect()
    cursor = conn.execute(
        "SELECT timestamp, question_redacted, cited_sources FROM audit_log "
        "WHERE cited_sources LIKE ? ORDER BY timestamp DESC",
        (f"%{source_filename}%",),
    )
    print_rows(cursor, ["timestamp", "question", "cited_sources"])
    conn.close()


def query_confidence_breakdown():
    print("\n--- Confidence level breakdown across all requests ---")
    conn = _connect()
    cursor = conn.execute(
        "SELECT confidence_level, COUNT(*) as n FROM audit_log GROUP BY confidence_level ORDER BY n DESC"
    )
    print_rows(cursor, ["confidence_level", "count"])
    conn.close()


def query_avg_latency_and_cost():
    print("\n--- Average latency and token usage across all requests ---")
    conn = _connect()
    cursor = conn.execute(
        "SELECT AVG(latency_sec), AVG(prompt_tokens), AVG(completion_tokens), COUNT(*) FROM audit_log"
    )
    row = cursor.fetchone()
    if row and row[3]:
        print(f"  Avg latency: {row[0]:.3f}s | Avg prompt tokens: {row[1]:.0f} | "
              f"Avg completion tokens: {row[2]:.0f} | Total requests: {row[3]}")
    else:
        print("  (no rows yet)")
    conn.close()


def main():
    import os
    if not os.path.exists(DB_PATH):
        print(f"No audit log found at {DB_PATH} yet — run agent.py against a live app.py first.")
        return

    args = sys.argv[1:]

    if not args:
        query_confidence_breakdown()
        query_refused()
        query_injections()
        query_validation_failures()
        query_output_redactions()
        query_slow()
        query_avg_latency_and_cost()
        return

    command = args[0]
    if command == "refused":
        query_refused()
    elif command == "injections":
        query_injections()
    elif command == "validation":
        query_validation_failures()
    elif command == "redactions":
        query_output_redactions()
    elif command == "slow":
        query_slow()
    elif command == "by-source" and len(args) > 1:
        query_by_source(args[1])
    else:
        print(f"Unknown command: {command}. See the module docstring for usage.")


if __name__ == "__main__":
    main()

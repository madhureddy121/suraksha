"""
agent.py

Suraksha — Ask the Trust-Wired Pipeline (Step 3 of 3)
=========================================================
5 hardcoded domain questions (Section F of the assignment), PLUS 4 demo
questions that specifically exercise the trust stack:

  - PII redaction on the way IN   (a phone number inside the question)
  - prompt-injection detection    (retrieves the real planted FAQ entry)
  - PII redaction on the way OUT  (simulate_pii_echo forces a leaky answer
                                   through the outgoing redaction stage)
  - a refusal for an out-of-scope question, with the trace checked to
    prove no LLM call happened at all

IMPORTANT: app.py must already be running in a separate terminal
(uvicorn app:app --reload --port 8000) before you run this file.

Run:
    python agent.py
"""
import requests

BASE_URL = "http://localhost:8000/ask"

DOMAIN_QUESTIONS = [
    "What MFA requirement applies to accessing company systems?",
    "Within what timeline must affected parties be notified after a confirmed breach?",
    "How do I report a suspected phishing attempt, and who is the named contact?",
    "Which security incidents in the log are still Open?",
    "What certification is required for a vendor handling customer data?",
]

# Deliberately includes a phone number, to demonstrate serving-time PII
# redaction on the QUESTION itself, before it's logged or sent anywhere.
PII_DEMO_QUESTION = (
    "My call-back number is 9876543210 — how do I report a suspected "
    "phishing email?"
)

# This retrieves the Security Awareness FAQ entry that was deliberately
# written to contain injection-style phrasing — a real end-to-end test,
# not a synthetic one.
INJECTION_DEMO_QUESTION = "What should I do if I receive a suspicious email?"

# Runs a normal question with simulate_pii_echo=true so the app appends a
# PII-shaped string to the raw answer and the outgoing redaction stage has
# something real to strip. The response shows output_pii_redacted.
PII_ECHO_DEMO_QUESTION = "What is the password length requirement?"

# No document covers this at all — should trigger the refusal guardrail.
OUT_OF_SCOPE_QUESTION = "What is our company's quarterly revenue for this year?"


def ask(question: str, **params) -> dict:
    response = requests.get(BASE_URL, params={"q": question, **params}, timeout=60)
    response.raise_for_status()
    return response.json()


def print_result(label: str, result: dict):
    print(f"\n{label}")
    print(f"Question (as logged)  : {result['question']}")
    print(f"Confidence            : {result['confidence']}")
    print(f"LLM called            : {result['llm_called']}")
    print(f"Injection flagged     : {result['injection_flagged']}")
    if result.get("injection_details"):
        print(f"Injection details     : {result['injection_details']}")
    print(f"Output validation OK  : {result['output_validation_passed']}")
    if result.get("output_validation_details"):
        print(f"Validation details    : {result['output_validation_details']}")
    if result.get("output_pii_redacted"):
        print(f"Output PII redacted   : {result['output_pii_redacted']}")
    print(f"Answer                : {result['answer']}")
    print(f"Sources               : {result['sources']}")
    print(f"Trace (per-stage sec) : {result['trace']}")


def main():
    print("=" * 64)
    print("Suraksha — NCS Telco+ IT Security Policy Trust & Compliance Pipeline")
    print("=" * 64)

    for i, question in enumerate(DOMAIN_QUESTIONS, start=1):
        try:
            result = ask(question)
        except requests.exceptions.ConnectionError:
            print("ERROR: Could not reach Suraksha. Is app.py running in another "
                  "terminal? (uvicorn app:app --reload --port 8000)")
            return
        print_result(f"Q{i}: {question}", result)

    print("\n" + "=" * 64)
    print("TRUST-STACK DEMONSTRATIONS")
    print("=" * 64)

    result = ask(PII_DEMO_QUESTION)
    print_result("PII DEMO (IN) — a phone number in the question itself", result)
    print("Notice: the question ABOVE should show [REDACTED_PHONE_INDIA],")
    print("not the real number you sent — that's serving-time redaction on the way in.")

    result = ask(INJECTION_DEMO_QUESTION)
    print_result("INJECTION DEMO — retrieves a real FAQ entry with injection-style text", result)
    print("Notice: injection_flagged should be True, with the exact phrases found —")
    print("and the answer should still just be a normal, safe FAQ answer.")

    result = ask(PII_ECHO_DEMO_QUESTION, simulate_pii_echo="true")
    print_result("PII DEMO (OUT) — deliberately provoked leaky answer", result)
    print("Notice: output_pii_redacted should show PHONE_INDIA being stripped from")
    print("the outgoing answer, which then contains [REDACTED_PHONE_INDIA].")

    result = ask(OUT_OF_SCOPE_QUESTION)
    print_result("REFUSAL DEMO — a question no document covers", result)
    print("Notice: confidence should be 'Refused', and no LLM call happened at all.")

    print("\n" + "=" * 64)
    print("Done! Run audit_query_tool.py next to see everything above")
    print("as real, queryable rows in the audit log.")
    print("=" * 64)


if __name__ == "__main__":
    main()

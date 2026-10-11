"""
app.py

Suraksha — the NCS Telco+ IT Security Policy Trust & Compliance RAG Backend (Step 2 of 3)
==============================================================================================
Wires the full trust stack around the basic retrieve-and-answer flow:

    PII-redact question (serving, in)
        -> retrieve
        -> confidence check / refusal (skips the LLM entirely)
        -> injection scan + untrusted-data wrapping
        -> context assembly
        -> LLM call (citation-required, injection-defended system prompt)
        -> PII-redact the OUTGOING answer (serving, out)
        -> output validation, incl. Suraksha's new citation-grounding check
        -> audit log write
        -> return response, with full confidence, flags, and per-stage trace

Run AFTER build_vectorstore.py:
    uvicorn app:app --reload --port 8000
"""
from dotenv import load_dotenv
from fastapi import FastAPI
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from openai import OpenAI

from context import assemble_context
from pii import redact_pii
from injection_defense import wrap_untrusted, check_retrieved_chunks, INJECTION_DEFENSE_SYSTEM_ADDENDUM
from output_validation import validate_answer, is_refusal, FALLBACK_MESSAGE
from confidence import confidence_level, should_refuse, best_score_from_results
from observability import Tracer
import audit_log

load_dotenv()

CHAT_MODEL = "gpt-5.4-mini"
EMBED_MODEL = "text-embedding-3-small"
COLLECTION_NAME = "suraksha_documents"
PERSIST_DIR = "./chroma_store"
TOP_K = 3

BASE_SYSTEM_PROMPT = """
You are Suraksha, the NCS Telco+ IT Security Policy Trust & Compliance
Document Q&A Assistant.

Tone: Precise, calm, and careful — this is security policy content, where
a wrong or unsourced answer is not a minor inconvenience.

Grounding rule: Only answer using the excerpts provided. Every factual
claim MUST be followed by a citation in the form (Source: <filename>).
If the excerpts don't cover the question, say so plainly and do not guess.
"""

SYSTEM_PROMPT = BASE_SYSTEM_PROMPT + INJECTION_DEFENSE_SYSTEM_ADDENDUM

# Trust-stack test harness for the OUTGOING-answer PII redaction stage.
# When /ask is called with simulate_pii_echo=true, this string is appended
# to the raw model answer BEFORE the redaction stage runs, simulating a
# model that echoed a phone number back from its context. It lets the
# outgoing redaction be demonstrated deterministically instead of hoping
# a real model leaks PII on cue. Clearly labelled in the response.
PII_ECHO_TEST_STRING = (
    "For the trust-stack test, the callback number on file is 9876543210."
)

client = OpenAI()
embeddings = OpenAIEmbeddings(model=EMBED_MODEL)
vectorstore = Chroma(
    collection_name=COLLECTION_NAME,
    embedding_function=embeddings,
    persist_directory=PERSIST_DIR,
)

app = FastAPI(title="Suraksha - IT Security Policy Trust & Compliance RAG Pipeline")


@app.get("/")
def root():
    return {"message": "Suraksha is running. Try /ask?q=your+question"}


@app.get("/ask")
def ask(q: str, top_k: int = TOP_K, simulate_pii_echo: bool = False):
    tracer = Tracer()

    # ---- 1. PII REDACTION, SERVING TIME, ON THE WAY IN ----
    with tracer.stage("pii_redact_input"):
        redacted_question, input_pii_counts = redact_pii(q)
        if input_pii_counts:
            print(f"[Suraksha] PII redacted from incoming question: {input_pii_counts}")

    # ---- 2. RETRIEVAL ----
    with tracer.stage("retrieval"):
        raw_results = vectorstore.similarity_search_with_relevance_scores(redacted_question, k=top_k)

    best_score = best_score_from_results(raw_results)
    level = confidence_level(best_score)

    # ---- 3. CONFIDENCE CHECK / REFUSAL (no LLM call happens on this path) ----
    if should_refuse(best_score):
        answer = "I don't know — none of the ingested documents cover this question confidently enough for me to answer."
        latency = tracer.total_seconds()
        audit_log.log_request(
            question_redacted=redacted_question,
            retrieved_sources=[doc.metadata.get("source") for doc, _ in raw_results],
            retrieved_scores=[round(s, 4) for _, s in raw_results],
            confidence_level="Refused",
            refused=True,
            llm_called=False,
            injection_flagged=False,
            injection_details="",
            output_validation_passed=None,
            output_validation_details="Skipped — refused before generation.",
            output_pii_redacted={},
            answer=answer,
            cited_sources=[],
            latency_sec=latency,
            prompt_tokens=0,
            completion_tokens=0,
            model=CHAT_MODEL,
        )
        return {
            "question": redacted_question,
            "answer": answer,
            "confidence": "Refused",
            "retrieved_chunks": [],
            "sources": [],
            "injection_flagged": False,
            "injection_details": [],
            "output_validation_passed": None,
            "output_validation_details": "Skipped — refused before generation.",
            "output_pii_redacted": {},
            "llm_called": False,
            "trace": tracer.as_dict(),
        }

    # ---- 4. INJECTION SCAN + UNTRUSTED-DATA WRAPPING ----
    with tracer.stage("injection_scan"):
        chunks_with_sources = [(doc.page_content, doc.metadata.get("source", "unknown")) for doc, _ in raw_results]
        injection_report = check_retrieved_chunks(chunks_with_sources)
        if injection_report["flagged"]:
            print(f"[Suraksha] INJECTION ATTEMPT FLAGGED in retrieved content: {injection_report['details']}")

    # ---- 5. CONTEXT ASSEMBLY (dedupe + pack), then wrap each piece as untrusted data ----
    with tracer.stage("context_assembly"):
        context_text, used_results = assemble_context(raw_results)
        wrapped_pieces = [
            wrap_untrusted(doc.page_content, doc.metadata.get("source", "unknown"))
            for doc, _ in used_results
        ]
        wrapped_context = "\n\n".join(wrapped_pieces)

    retrieved_chunks = [
        {
            "source": doc.metadata.get("source", "unknown"),
            "score": round(float(score), 4),
            "text_preview": doc.page_content[:150] + ("..." if len(doc.page_content) > 150 else ""),
        }
        for doc, score in used_results
    ]
    # The sources the model actually saw — the ground truth for citation checking.
    retrieved_source_names = sorted({doc.metadata.get("source", "unknown") for doc, _ in used_results})

    user_prompt = (
        f"Question: {redacted_question}\n\n"
        f"Retrieved excerpts:\n{wrapped_context}\n\n"
        "Answer using only the excerpts above. Cite each fact as (Source: <filename>)."
    )

    # ---- 6. LLM CALL ----
    with tracer.stage("llm_call"):
        response = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
    raw_answer = response.choices[0].message.content
    usage = response.usage

    if simulate_pii_echo:
        # Deliberately provoke a leaky answer so the OUT redaction can be
        # demonstrated — see PII_ECHO_TEST_STRING above.
        raw_answer = f"{raw_answer}\n\n{PII_ECHO_TEST_STRING}"
        print("[Suraksha] simulate_pii_echo=true — a PII-shaped string was appended "
              "to the raw answer to exercise the outgoing redaction stage.")

    # ---- 7. PII REDACTION, SERVING TIME, ON THE WAY OUT ----
    with tracer.stage("pii_redact_output"):
        cleaned_answer, output_pii_counts = redact_pii(raw_answer)
        if output_pii_counts:
            print(f"[Suraksha] PII redacted from the OUTGOING answer: {output_pii_counts}")

    # ---- 8. OUTPUT VALIDATION (5 checks, incl. citation grounding) ----
    with tracer.stage("output_validation"):
        validation = validate_answer(cleaned_answer, retrieved_sources=retrieved_source_names)
        if validation["passed"]:
            final_answer = cleaned_answer
        else:
            print(f"[Suraksha] OUTPUT VALIDATION FAILED: {validation['details']}")
            final_answer = FALLBACK_MESSAGE

    cited_sources = sorted(set(doc.metadata.get("source", "unknown") for doc, _ in used_results)) \
        if not is_refusal(final_answer) else []

    # ---- 9. AUDIT LOG ----
    latency = tracer.total_seconds()
    audit_log.log_request(
        question_redacted=redacted_question,
        retrieved_sources=[c["source"] for c in retrieved_chunks],
        retrieved_scores=[c["score"] for c in retrieved_chunks],
        confidence_level=level,
        refused=False,
        llm_called=True,
        injection_flagged=injection_report["flagged"],
        injection_details=str(injection_report["details"]),
        output_validation_passed=validation["passed"],
        output_validation_details=validation["details"],
        output_pii_redacted=output_pii_counts,
        answer=final_answer,
        cited_sources=cited_sources,
        latency_sec=latency,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        model=CHAT_MODEL,
    )

    return {
        "question": redacted_question,
        "answer": final_answer,
        "confidence": level,
        "retrieved_chunks": retrieved_chunks,
        "sources": cited_sources,
        "injection_flagged": injection_report["flagged"],
        "injection_details": injection_report["details"],
        "output_validation_passed": validation["passed"],
        "output_validation_details": validation["details"],
        "output_pii_redacted": output_pii_counts,
        "llm_called": True,
        "trace": tracer.as_dict(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

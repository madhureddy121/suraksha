"""
observability.py

Suraksha — Tracing Every Stage: Retrieval, Generation, Latency, Cost
========================================================================
"Observability" means being able to answer "what actually happened
inside this one request?" after the fact, not just "did it work?" — every
stage of the pipeline gets its own timing entry, collected into a single
trace object attached to that request's API response and audit log row.

A NOTE ON LANGSMITH: the official tool list for this module includes
LangSmith, a hosted tracing and observability platform with a full web UI
over exactly this kind of data. This lab implements the SAME underlying
idea with a lightweight, dependency-free local Tracer class, so it runs
completely offline and for free. To use LangSmith for real, set these two
environment variables (see .env.example) and LangChain's own
instrumentation picks it up automatically, with no code changes needed:

    LANGCHAIN_TRACING_V2=true
    LANGCHAIN_API_KEY=your-langsmith-key
"""
import time


class Tracer:
    """Collects named stage timings for ONE request. Usage:

        tracer = Tracer()
        with tracer.stage("retrieval"):
            ... do retrieval ...
        with tracer.stage("llm_call"):
            ... call the model ...
        print(tracer.as_dict())
    """

    def __init__(self):
        self.stages = {}

    def stage(self, name: str):
        return _StageTimer(self, name)

    def as_dict(self) -> dict:
        return dict(self.stages)

    def total_seconds(self) -> float:
        return sum(self.stages.values())


class _StageTimer:
    def __init__(self, tracer: Tracer, name: str):
        self.tracer = tracer
        self.name = name

    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, *args):
        self.tracer.stages[self.name] = round(time.time() - self._start, 4)

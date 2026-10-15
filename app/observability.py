"""LangSmith helpers. Tracing itself is switched on by env (LANGSMITH_TRACING, LANGSMITH_API_KEY, LANGSMITH_PROJECT).

LangGraph traces every node and every LangChain LLM call automatically. `traceable` adds named spans for
non-LangChain work (the Pinecone search), so retrieval shows up as its own run in the trace tree.
Falls back to a no-op decorator when langsmith is not installed (unit tests).
"""
try:
    from langsmith import traceable  # type: ignore
except ImportError:  # pragma: no cover
    def traceable(*dargs, **dkwargs):
        if len(dargs) == 1 and callable(dargs[0]) and not dkwargs:
            return dargs[0]

        def deco(fn):
            return fn
        return deco


def turn_config(session_id: str, user_id: str, role: str, request_id: str) -> dict:
    """Run config for one conversation turn. `thread_id` groups all turns of a session into one LangSmith thread."""
    return {
        "configurable": {"thread_id": session_id},
        "run_name": "assistant_turn",
        "tags": [f"role:{role}", "bank-assistant"],
        "metadata": {"thread_id": session_id, "session_id": session_id, "user_id": user_id,
                     "role": role, "request_id": request_id},
    }

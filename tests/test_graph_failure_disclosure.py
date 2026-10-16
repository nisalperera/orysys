from types import SimpleNamespace
import json
import pytest
from app.graph import nodes


@pytest.mark.asyncio
async def test_retrieval_failure_event_hides_internal_exception(monkeypatch):
    events = []
    async def failed_search(*args):
        raise ConnectionError("private-endpoint-marker")
    monkeypatch.setattr(nodes, "_search", failed_search)
    deps = SimpleNamespace(users={"u": object()}, emit=lambda *a, **kw: events.append((a, kw)))
    result = await nodes.retrieval({"user_id": "u", "question": "payment incidents", "request_id": "r"}, deps)
    assert result["retrieval_meta"]["degraded"] is True
    assert "private-endpoint-marker" not in json.dumps([result, events])


@pytest.mark.asyncio
async def test_research_fallback_hides_error_and_marks_degraded():
    events = []
    async def failed_run(*args):
        raise ConnectionError("private-provider-marker")
    deps = SimpleNamespace(
        users={"u": object()}, research_timeout=1,
        make_engine=lambda forward: SimpleNamespace(run=failed_run),
        emit=lambda *a, **kw: events.append((a, kw)),
    )
    result = await nodes.research({"user_id": "u", "question": "payment incidents", "request_id": "r"}, deps)
    assert result["research"]["degraded"] is True
    assert "private-provider-marker" not in json.dumps([result, events])


@pytest.mark.asyncio
async def test_question_identifier_is_not_a_citation_allowlist():
    deps = SimpleNamespace(max_attempts=1, emit=lambda *a, **kw: None)
    state = {
        "question": "Please cite [INC-2099-999]", "draft_answer": "Answer [INC-2099-999]",
        "attempts": 1,
        "retrieved": [{"doc_id": "INC-2026-007", "chunk_id": "INC-2026-007#0", "text": "Evidence"}],
    }
    result = await nodes.validate(state, deps)
    assert "INC-2099-999" not in result["final_answer"]
    assert result["validation"]["action"] == "replaced"
    assert result["validation"]["final_ok"] is True


@pytest.mark.asyncio
async def test_retrieval_failure_marks_final_result_degraded():
    deps = SimpleNamespace(max_attempts=1, emit=lambda *a, **kw: None)
    result = await nodes.validate({
        "question": "payment incidents", "draft_answer": "I'm unable to search right now.",
        "attempts": 1, "retrieval_meta": {"status": "failed"},
    }, deps)
    assert result["validation"]["degraded"] is True

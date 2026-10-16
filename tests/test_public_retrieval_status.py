import json
from types import SimpleNamespace
import pytest
from app.security.public_status import public_degradation_reasons
from app.graph import nodes


def test_degradation_reasons_do_not_echo_provider_details():
    result = public_degradation_reasons([
        "sparse encoder failed, dense only: private-marker",
        "namespace 'incident' failed: private-marker",
        "private-marker",
    ])
    assert result and "private-marker" not in json.dumps(result)


@pytest.mark.asyncio
async def test_successful_but_degraded_retrieval_sanitizes_activity(monkeypatch):
    events = []
    async def search(*args):
        return SimpleNamespace(
            hits=[], namespaces_searched=["incident"], failed_namespaces=[], degraded=True,
            degraded_reasons=["sparse encoder failed, dense only: private-marker"],
            no_relevant_results=True, dropped_by_doc_cap=0, dropped_below_min_score=0,
            alpha=0.6, embed_ms=1, query_ms=1,
        )
    monkeypatch.setattr(nodes, "_search", search)
    deps = SimpleNamespace(users={"u": object()}, emit=lambda *a, **kw: events.append((a, kw)))
    result = await nodes.retrieval({"user_id": "u", "question": "payment incidents"}, deps)
    assert result["retrieval_meta"]["degraded"] is True
    assert "private-marker" not in json.dumps([result, events])

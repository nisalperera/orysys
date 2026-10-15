import asyncio
from datetime import date

import pytest
from pydantic import ValidationError

from app.auth.models import USERS
from app.retrieval.cache import CachedEmbedder
from app.retrieval.filters import build_filter, namespaces_for
from app.retrieval.hybrid import HybridRetriever, RetrievalError, apply_post_filters, scale_hybrid
from app.retrieval.schemas import Hit, SearchRequest

NS = ("incident", "runbook", "policy")


def _m(i, score, level, ns, chunk=0):
    return {"id": f"{i}#{chunk}", "score": score, "metadata": {
        "doc_id": i, "title": f"T {i}", "section": "s", "document_type": ns, "department": "payments",
        "access_level": level, "created_date": "2026-01-01", "text": "x"}}


class FakeIndex:
    def __init__(self, data, fail=()):
        self.data, self.fail, self.calls = data, set(fail), []

    def query(self, **kw):
        self.calls.append(kw)
        if kw["namespace"] in self.fail:
            raise TimeoutError("boom")
        return {"matches": self.data.get(kw["namespace"], [])}


async def _embed(q):
    return [1.0, 2.0]


def _ret(index, sparse=lambda q: {"indices": [1], "values": [4.0]}, **kw):
    return HybridRetriever(index, _embed, sparse, NS, default_alpha=0.5, namespace_timeout_sec=2, **kw)


def run(c):
    return asyncio.run(c)


def _hit(i, score, level="internal"):
    return Hit(chunk_id=f"{i}#0", doc_id=i, title="t", section="s", document_type="incident", department="d",
               access_level=level, created_date="2026-01-01", score=score, text="x")


def test_scale_hybrid_convex():
    d, s = scale_hybrid([1.0, 2.0], {"indices": [3], "values": [4.0]}, 0.25)
    assert d == [0.25, 0.5] and s["values"] == [3.0]
    assert scale_hybrid([1.0], None, 0.25) == ([1.0], None)


def test_rbac_filter_per_role():
    req = SearchRequest(query="payments")
    assert build_filter(USERS["viewer1"], req) == {"access_level": {"$in": ["public", "internal"]}}
    assert "restricted" in build_filter(USERS["admin1"], req)["access_level"]["$in"]


def test_filter_combines_and_cannot_widen():
    req = SearchRequest(query="payments", department="payments", date_from=date(2025, 10, 16), date_to=date(2026, 10, 16))
    f = build_filter(USERS["viewer1"], req)
    assert f["$and"][0] == {"access_level": {"$in": ["public", "internal"]}} and len(f["$and"]) == 4


def test_request_validation():
    for bad in (dict(query="x"), dict(query="ok query", document_types=["secrets"]),
                dict(query="ok query", department="a; DROP"), dict(query="ok query", top_k=500),
                dict(query="ok query", date_from=date(2026, 2, 1), date_to=date(2026, 1, 1))):
        with pytest.raises(ValidationError):
            SearchRequest(**bad)


def test_namespace_targeting():
    assert namespaces_for(SearchRequest(query="runbook?", document_types=["runbook"]), NS) == ["runbook"]
    assert namespaces_for(SearchRequest(query="anything"), NS) == list(NS)


def test_merge_sort_topk_and_leak_blocked():
    idx = FakeIndex({"incident": [_m("A", 0.9, "internal", "incident"), _m("L", 0.99, "restricted", "incident")],
                     "runbook": [_m("B", 0.7, "internal", "runbook")]})
    res = run(_ret(idx).search(USERS["viewer1"], SearchRequest(query="pool exhaustion", top_k=5)))
    assert [h.doc_id for h in res.hits] == ["A", "B"]
    assert all(c["filter"] == {"access_level": {"$in": ["public", "internal"]}} for c in idx.calls)


def test_admin_sees_restricted():
    idx = FakeIndex({"policy": [_m("P", 0.5, "restricted", "policy")]})
    res = run(_ret(idx).search(USERS["admin1"], SearchRequest(query="remuneration policy")))
    assert [h.doc_id for h in res.hits] == ["P"]


def test_partial_failure_degrades_gracefully():
    idx = FakeIndex({"incident": [_m("A", 0.9, "internal", "incident")]}, fail=["runbook"])
    res = run(_ret(idx).search(USERS["viewer1"], SearchRequest(query="pool exhaustion")))
    assert res.degraded and res.failed_namespaces == ["runbook"] and res.hits


def test_total_and_embedding_failure_raise():
    with pytest.raises(RetrievalError):
        run(_ret(FakeIndex({}, fail=NS)).search(USERS["viewer1"], SearchRequest(query="pool exhaustion")))

    async def bad(q):
        raise ConnectionError("down")
    with pytest.raises(RetrievalError):
        run(HybridRetriever(FakeIndex({}), bad, None, NS).search(USERS["viewer1"], SearchRequest(query="pool exhaustion")))


def test_no_sparse_falls_back_to_dense():
    idx = FakeIndex({"incident": [_m("A", 0.9, "internal", "incident")]})
    res = run(_ret(idx, sparse=None).search(USERS["viewer1"], SearchRequest(query="pool exhaustion", document_types=["incident"])))
    assert res.degraded and "sparse_vector" not in idx.calls[0]


def test_min_score_floor_sets_no_relevant_flag():
    idx = FakeIndex({"meeting_notes": [], "incident": [_m("A", 0.17, "internal", "incident"), _m("B", 0.16, "internal", "incident")]})
    res = run(_ret(idx, min_score=0.30).search(USERS["viewer1"], SearchRequest(query="executive compensation")))
    assert res.hits == [] and res.no_relevant_results and res.dropped_below_min_score == 2


def test_min_score_keeps_strong_hits():
    idx = FakeIndex({"incident": [_m("A", 0.65, "internal", "incident"), _m("B", 0.17, "internal", "incident")]})
    res = run(_ret(idx, min_score=0.30).search(USERS["viewer1"], SearchRequest(query="pool exhaustion")))
    assert [h.doc_id for h in res.hits] == ["A"] and not res.no_relevant_results


def test_max_per_doc_cap_and_overfetch():
    idx = FakeIndex({"incident": [_m("A", 0.9, "internal", "incident", 1), _m("A", 0.8, "internal", "incident", 2),
                                  _m("A", 0.7, "internal", "incident", 3), _m("B", 0.6, "internal", "incident")]})
    res = run(_ret(idx, max_per_doc=2).search(USERS["viewer1"], SearchRequest(query="pool exhaustion", top_k=3, document_types=["incident"])))
    assert [h.chunk_id for h in res.hits] == ["A#1", "A#2", "B#0"] and res.dropped_by_doc_cap == 1
    assert idx.calls[0]["top_k"] == 6


def test_post_filter_pure():
    hits = [_hit("A", 0.9), _hit("L", 0.95, "restricted"), _hit("B", 0.1)]
    final, leaked, below, capped = apply_post_filters(hits, {"internal"}, 0.3, 2, 5)
    assert [h.doc_id for h in final] == ["A"] and (leaked, below, capped) == (1, 1, 0)


def test_timings_reported():
    idx = FakeIndex({"incident": [_m("A", 0.9, "internal", "incident")]})
    res = run(_ret(idx).search(USERS["viewer1"], SearchRequest(query="pool exhaustion")))
    assert res.latency_ms >= res.embed_ms >= 0 and res.query_ms >= 0


def test_embedding_cache():
    calls = []

    async def fn(q):
        calls.append(q)
        return [1.0]
    c = CachedEmbedder(fn, max_size=2)
    run(c("Pool  Exhaustion")); run(c("pool exhaustion")); run(c("a")); run(c("b")); run(c("pool exhaustion"))
    assert c.hits == 1 and len(calls) == 4

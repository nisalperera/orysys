import asyncio
from types import SimpleNamespace

import pytest

from app.auth.models import USERS
from app.llm import build_llm_kwargs, is_openrouter
from app.retrieval.cache import CachedEmbedder
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.schemas import SearchRequest
from app.rlm.errors import http_status, is_permanent

NS = ("incident", "runbook")


def _m(doc, chunk, score, level="internal"):
    return {"id": f"{doc}#{chunk}", "score": score, "metadata": {
        "doc_id": doc, "title": "t", "section": "s", "document_type": "incident", "department": "payments",
        "access_level": level, "created_date": "2026-01-01", "text": "x"}}


class FakeIndex:
    def __init__(self, matches):
        self.matches, self.calls = matches, []

    def query(self, **kw):
        self.calls.append(kw)
        return {"matches": self.matches if kw["namespace"] == "incident" else []}


async def _embed(q):
    return [1.0]


def _retriever(idx):
    return HybridRetriever(idx, _embed, None, NS, min_score=0.30, max_per_doc=2, namespace_timeout_sec=2)


def run(c):
    return asyncio.run(c)


ALL = [_m("A", i, 0.9 - i * 0.01) for i in range(4)] + [_m("B", 0, 0.1)]


def test_targeted_search_keeps_all_chunks_and_weak_scores():
    idx = FakeIndex(ALL)
    res = run(_retriever(idx).search(USERS["analyst1"], SearchRequest(query="root cause", top_k=10, doc_ids=["A", "B"])))
    assert len(res.hits) == 5 and res.min_score == 0.0 and res.dropped_by_doc_cap == 0
    assert idx.calls[0]["top_k"] == 10  # no over-fetch when the cap is off


def test_untargeted_search_still_applies_floor_and_cap():
    idx = FakeIndex(ALL)
    res = run(_retriever(idx).search(USERS["analyst1"], SearchRequest(query="root cause", top_k=10)))
    assert [h.chunk_id for h in res.hits] == ["A#0", "A#1"] and res.min_score == 0.30
    assert res.dropped_by_doc_cap == 2 and res.dropped_below_min_score == 1


def test_targeted_search_still_enforces_access():
    idx = FakeIndex([_m("A", 0, 0.9), _m("L", 0, 0.99, "restricted")])
    res = run(_retriever(idx).search(USERS["viewer1"], SearchRequest(query="root cause", doc_ids=["A", "L"])))
    assert [h.doc_id for h in res.hits] == ["A"]
    assert {"doc_id": {"$in": ["A", "L"]}} in idx.calls[0]["filter"]["$and"]


def test_cache_shares_inflight_calls():
    calls = []

    async def slow(q):
        calls.append(q)
        await asyncio.sleep(0.05)
        return [1.0, 2.0]

    async def main():
        c = CachedEmbedder(slow)
        out = await asyncio.gather(*(c("Payment  Failures") for _ in range(3)), c("payment failures"))
        return c, out

    c, out = run(main())
    assert len(calls) == 1 and all(o == [1.0, 2.0] for o in out) and c.misses == 1 and c.hits == 3
    assert not c._inflight


def test_cache_does_not_store_failures():
    state = {"n": 0}

    async def flaky(q):
        state["n"] += 1
        if state["n"] == 1:
            raise ConnectionError("down")
        return [1.0]

    async def main():
        c = CachedEmbedder(flaky)
        with pytest.raises(ConnectionError):
            await c("q")
        await asyncio.sleep(0)
        return await c("q"), c

    vec, c = run(main())
    assert vec == [1.0] and state["n"] == 2


def _s(url):
    return SimpleNamespace(base_url=url, llm_model="m", llm_api_key="k", llm_max_tokens=10, llm_timeout_sec=5,
                           llm_max_retries=1, api_key="k",)


def test_llm_kwargs_openrouter_vs_vllm():
    assert is_openrouter("https://openrouter.ai/api/v1") and not is_openrouter("http://localhost:8000/v1")
    o_off = build_llm_kwargs(_s("https://openrouter.ai/api/v1"), thinking=False)["extra_body"]
    o_on = build_llm_kwargs(_s("https://openrouter.ai/api/v1"), thinking=True)["extra_body"]
    assert o_off["reasoning"] == {"effort": "none"} and o_on["reasoning"] == {"enabled": True}
    assert "chat_template_kwargs" not in o_off and o_off["top_k"] == 20
    v = build_llm_kwargs(_s("http://localhost:8000/v1"), thinking=True)["extra_body"]
    assert v["chat_template_kwargs"] == {"enable_thinking": True} and "reasoning" not in v
    assert build_llm_kwargs(_s("x"), temperature=0.0)["temperature"] == 0.0


def test_permanent_error_classification():
    class E(Exception):
        status_code = 429
    assert not is_permanent(E("rate limited")) and is_permanent(Exception("Error code: 400 - not a valid model ID"))
    e = Exception("x"); e.status_code = 401
    assert is_permanent(e) and http_status(Exception("boom")) is None

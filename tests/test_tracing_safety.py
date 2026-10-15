import asyncio

from tests.graph_helpers import FakeSearch, SimpleGraph, make_deps, turn


def _run(deps, question="pool incident?"):
    return asyncio.run(turn(SimpleGraph(deps), deps, "viewer1", question))


def test_langsmith_error_does_not_break_retrieval(monkeypatch):
    class LangSmithUserError(Exception):
        pass

    LangSmithUserError.__module__ = "langsmith.utils"

    def failing_traceable(*a, **k):
        def deco(fn):
            async def wrapper(*args, **kwargs):
                raise LangSmithUserError("A run is addressed by project or by address, not both")
            return wrapper
        return deco

    monkeypatch.setattr("app.graph.nodes.traceable", failing_traceable)
    deps = make_deps()
    res, ev = _run(deps)
    assert "unable to search" not in res["final_answer"] and deps.fakes.search.calls
    assert [e for e in ev if e["type"] == "retrieval"][0]["data"]["status"] == "ok"


def test_real_search_errors_are_still_reported(monkeypatch):
    deps = make_deps(search=FakeSearch(error=RuntimeError("pinecone down")))
    res, _ = _run(deps)
    assert "unable to search" in res["final_answer"]

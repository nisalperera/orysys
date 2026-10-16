from types import SimpleNamespace
import pytest
import app.trace_safety as tracing
from app.graph.nodes import _search


class MonitoringError(Exception):
    pass

MonitoringError.__module__ = "langsmith.errors"


@pytest.mark.asyncio
async def test_outer_retrieval_trace_failure_does_not_repeat_search(monkeypatch):
    calls = []
    def failing_trace(**options):
        def decorate(function):
            async def wrapped():
                await function()
                raise MonitoringError("private-monitoring-error")
            return wrapped
        return decorate
    monkeypatch.setattr(tracing, "traceable", failing_trace)
    async def search(*args):
        calls.append(True)
        return "evidence"
    deps = SimpleNamespace(search=search, search_timeout=1)
    user = SimpleNamespace(role=SimpleNamespace(value="viewer"))
    req = SimpleNamespace(query="question", model_dump=lambda **kw: {})
    assert await _search(deps, user, req) == "evidence"
    assert calls == [True]

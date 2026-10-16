import asyncio
import json
from types import SimpleNamespace
import pytest
from app.graph.runtime import wrap_node


@pytest.mark.asyncio
async def test_node_error_event_does_not_expose_exception():
    events = []
    deps = SimpleNamespace(emit=lambda *args, **kwargs: events.append((args, kwargs)))
    async def failed(state, deps):
        raise RuntimeError("private-endpoint-marker")
    result = await wrap_node("retrieval", failed, deps)({"request_id": "r"})
    errors = [data for args, data in events if args[1] == "node_error"]
    assert errors == [{"error": "node_execution_failed"}]
    assert result["node_errors"] == ["retrieval: node_execution_failed"]
    assert "private-endpoint-marker" not in json.dumps([events, result])


@pytest.mark.asyncio
async def test_node_wrapper_preserves_cancellation():
    events = []
    deps = SimpleNamespace(emit=lambda *args, **kwargs: events.append((args, kwargs)))
    async def cancelled(state, deps):
        raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await wrap_node("research", cancelled, deps)({"request_id": "r"})
    assert not any(args[1] == "node_error" for args, _ in events)

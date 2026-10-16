from types import SimpleNamespace
import time
import pytest
from app.api.service import ChatService
from app.graph import nodes


def test_final_validation_status_is_in_api_payload():
    payload = ChatService._payload({"validation": {
        "ok": False, "final_ok": True, "action": "replaced", "issues": [],
    }}, "request", time.perf_counter())
    assert payload["validation"]["ok"] is False
    assert payload["validation"]["final_ok"] is True


@pytest.mark.asyncio
async def test_terminal_validation_activity_includes_final_status():
    events = []
    deps = SimpleNamespace(max_attempts=1, emit=lambda *a, **kw: events.append((a, kw)))
    result = await nodes.validate({"question": "hello", "draft_answer": "Hello!", "attempts": 1}, deps)
    terminal = [data for args, data in events if args[1:3] == ("validation", "validate")][-1]
    assert terminal["final_ok"] == result["validation"]["final_ok"]

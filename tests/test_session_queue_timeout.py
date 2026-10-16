from types import SimpleNamespace
import pytest
from app.api.service import ChatService


@pytest.mark.asyncio
async def test_turn_timeout_includes_wait_for_session_lock():
    calls = []
    async def invoke(*args):
        calls.append(True)
        return {"final_answer": "unexpected"}
    deps = SimpleNamespace(buses={})
    service = ChatService(SimpleNamespace(ainvoke=invoke), deps, turn_timeout=0.01)
    user = SimpleNamespace(user_id="viewer1", role=SimpleNamespace(value="viewer"))
    lock = service.sessions.lock("queue-test-session")
    await lock.acquire()
    try:
        final = await service.ask(user, "queue-test-session", "hello")
        assert final["degraded"] is True
        assert calls == []
        assert lock.locked()
    finally:
        lock.release()
    assert deps.buses == {}

"""Chat service: runs one graph turn per request and exposes the activity events as an async stream.

Independent of FastAPI so it can be tested (and reused by the Streamlit app) without a web server.
Concurrency: turns in the same session are serialised by a lock (the checkpointer state is per session).
"""
import asyncio
import logging
import time
import uuid
from typing import AsyncIterator

from app.graph.deps import Deps
from app.graph.events import EventBus
from app.observability import turn_config

log = logging.getLogger("api")
APOLOGY = "Something went wrong while processing your request. Please try again."


class SessionStore:
    """Binds a session to its first user. Prevents one user from reading another user's conversation memory."""

    def __init__(self):
        self._owner: dict[str, str] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def bind(self, session_id: str, user_id: str) -> None:
        if self._owner.setdefault(session_id, user_id) != user_id:
            raise PermissionError("session belongs to another user")

    def lock(self, session_id: str) -> asyncio.Lock:
        return self._locks.setdefault(session_id, asyncio.Lock())


class ChatService:
    def __init__(self, graph, deps: Deps, sessions: SessionStore | None = None, turn_timeout: float = 240.0):
        self.graph, self.deps, self.sessions, self.turn_timeout = graph, deps, sessions or SessionStore(), turn_timeout

    def check_session(self, user, session_id: str) -> None:
        self.sessions.bind(session_id, user.user_id)

    async def stream(self, user, session_id: str, message: str) -> AsyncIterator[dict]:
        self.check_session(user, session_id)
        rid = uuid.uuid4().hex[:12]
        bus = EventBus(rid)
        self.deps.buses[rid] = bus
        task = asyncio.create_task(self._run(user, session_id, message, rid, bus))
        try:
            async for ev in bus:
                yield ev
        finally:
            if not task.done():  # client disconnected: stop the graph, do not leak work
                task.cancel()
            self.deps.buses.pop(rid, None)
            await asyncio.gather(task, return_exceptions=True)

    async def ask(self, user, session_id: str, message: str) -> dict:
        final: dict = {}
        async for ev in self.stream(user, session_id, message):
            if ev["type"] == "final":
                final = ev["data"]
        return final

    async def _run(self, user, session_id: str, message: str, rid: str, bus: EventBus) -> None:
        lock = self.sessions.lock(session_id)
        if lock.locked():
            bus.emit("state", None, label="Waiting for the previous request in this session")
        t0 = time.perf_counter()
        try:
            async with lock:
                result = await asyncio.wait_for(
                    self.graph.ainvoke({"request_id": rid, "user_id": user.user_id, "question": message},
                                       turn_config(session_id, user.user_id, user.role.value, rid)),
                    self.turn_timeout)
            bus.emit("final", None, **self._payload(result, rid, t0))
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001  never leak internals to the client
            log.exception("turn failed", extra={"extra_fields": {"request_id": rid, "session_id": session_id}})
            bus.emit("error", None, message="internal error", request_id=rid)
            bus.emit("final", None, answer=APOLOGY, citations=[], degraded=True, request_id=rid, intent=None,
                     blocked=False, validation={}, latency_ms=int((time.perf_counter() - t0) * 1000))
        finally:
            bus.close()

    @staticmethod
    def _payload(result: dict, rid: str, t0: float) -> dict:
        val = result.get("validation") or {}
        return {"answer": result.get("final_answer", ""), "citations": result.get("citations", []),
                "intent": (result.get("route") or {}).get("intent"), "blocked": bool(result.get("blocked_reason")),
                "degraded": bool(val.get("degraded")) or bool(result.get("node_errors")),
                "validation": {"ok": val.get("ok"), "action": val.get("action"), "issues": val.get("issues", [])},
                "attempts": result.get("attempts", 0), "request_id": rid,
                "latency_ms": int((time.perf_counter() - t0) * 1000)}

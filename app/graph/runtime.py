"""Node wrapper shared by the LangGraph builder and the test runner: activity events, timing, error isolation."""
import asyncio
import logging
import time

from app.graph.events import STATE_LABELS

log = logging.getLogger("graph")


def wrap_node(name: str, fn, deps):
    async def runner(state: dict) -> dict:
        rid = state.get("request_id", "-")
        deps.emit(rid, "node_start", name)
        deps.emit(rid, "state", name, label=STATE_LABELS.get(name, name))
        t0 = time.perf_counter()
        try:
            update = await fn(state, deps)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001  one failing node must not kill the turn
            log.exception("node %s failed", name)
            deps.emit(rid, "node_error", name, error=f"{type(exc).__name__}: {exc}"[:300])
            update = {"node_errors": (state.get("node_errors") or []) + [f"{name}: {type(exc).__name__}"]}
        deps.emit(rid, "node_end", name, ms=int((time.perf_counter() - t0) * 1000))
        return update

    runner.__name__ = name
    return runner

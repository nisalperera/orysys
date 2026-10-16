"""Activity events: what the Streamlit Agent Activity Panel renders.

Event types
  node_start / node_end / node_error   active LangGraph node (with duration)
  state                                human readable agent state ("Searching knowledge base")
  input_guard, routing, policy         validation and routing decisions
  retrieval_start / retrieval          retrieval status
  rlm.*                                research agent steps (plan, select, batches, recurse, reduce)
  tool_call                            authorized tool executions
  generation_start / token             response generation (tokens are provisional until `final`)
  validation                           guardrail results
  memory_loaded / memory_updated       memory
  final / error                        authoritative answer / failure
"""
import asyncio
from datetime import datetime, timezone


class EventBus:
    """One bus per request. Nodes emit synchronously, the API drains it as an async iterator."""

    def __init__(self, request_id: str):
        self.request_id = request_id
        self._q: asyncio.Queue = asyncio.Queue()
        self._seq = 0
        self.closed = False

    def emit(self, type_: str, node: str | None = None, **data) -> None:
        if self.closed:
            return
        self._seq += 1
        self._q.put_nowait({"seq": self._seq, "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                            "type": type_, "node": node, "data": data})

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self._q.put_nowait(None)

    def __aiter__(self):
        return self

    async def __anext__(self) -> dict:
        item = await self._q.get()
        if item is None:
            raise StopAsyncIteration
        return item

    def drain(self) -> list[dict]:
        """Non-blocking read of everything queued so far (tests, debugging)."""
        out = []
        while not self._q.empty():
            item = self._q.get_nowait()
            if item is not None:
                out.append(item)
        return out


STATE_LABELS = {
    "guard_input": "Validating request",
    "supervisor": "Understanding intent and routing",
    "retrieval": "Searching knowledge base",
    "research": "Researching across documents",
    "response": "Generating response",
    "validate": "Validating answer",
    "blocked": "Request blocked by input guard",
    "update_memory": "Updating memory",
}

"""Server-Sent Events formatting and a keep-alive wrapper."""
import asyncio
import json
from typing import AsyncIterator


def format_sse(ev: dict) -> str:
    return f"id: {ev['seq']}\nevent: {ev['type']}\ndata: {json.dumps(ev, default=str)}\n\n" if "seq" in ev \
        else f"event: {ev['type']}\ndata: {json.dumps(ev, default=str)}\n\n"


async def sse_iter(events: AsyncIterator[dict], keepalive: float = 15.0) -> AsyncIterator[str]:
    """Yields SSE frames and a comment ping when idle (proxies close silent connections).

    The pending `__anext__` is awaited with asyncio.wait, not wait_for: cancelling an async generator step on timeout
    would terminate the generator."""
    it = events.__aiter__()
    pending = None
    try:
        while True:
            if pending is None:
                pending = asyncio.ensure_future(it.__anext__())
            done, _ = await asyncio.wait({pending}, timeout=keepalive)
            if not done:
                yield ": ping\n\n"
                continue
            task, pending = pending, None
            try:
                ev = task.result()
            except StopAsyncIteration:
                return
            yield format_sse(ev)
    finally:
        if pending is not None:
            pending.cancel()
        aclose = getattr(it, "aclose", None)
        if aclose:
            await aclose()

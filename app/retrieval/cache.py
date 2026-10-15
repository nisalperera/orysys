"""LRU cache for query embeddings with in-flight sharing (RAG stage: embed).

Embedding through a remote API is the slowest step of a search (seconds). Two situations repeat the same query:
a user re-asking, and the RLM running several batch sub-agents at once with the same question. The LRU handles
the first, and sharing the pending call handles the second: concurrent requests for one query trigger ONE API call.
Keys are normalised (trim, lowercase, collapsed spaces). Failed calls are not cached.
"""
import asyncio
from collections import OrderedDict
from typing import Awaitable, Callable


class CachedEmbedder:
    def __init__(self, fn: Callable[[str], Awaitable[list[float]]], max_size: int = 256):
        self._fn, self._max = fn, max_size
        self._store: OrderedDict[str, list[float]] = OrderedDict()
        self._inflight: dict[str, asyncio.Future] = {}
        self.hits = 0
        self.misses = 0

    @staticmethod
    def _key(q: str) -> str:
        return " ".join(q.lower().split())

    async def __call__(self, query: str) -> list[float]:
        key = self._key(query)
        if key in self._store:
            self._store.move_to_end(key)
            self.hits += 1
            return list(self._store[key])
        if key in self._inflight:
            self.hits += 1
            return list(await asyncio.shield(self._inflight[key]))
        self.misses += 1
        fut = asyncio.ensure_future(self._fn(query))
        self._inflight[key] = fut
        fut.add_done_callback(lambda _f, k=key: self._inflight.pop(k, None))
        vec = await asyncio.shield(fut)
        self._store[key] = list(vec)
        if len(self._store) > self._max:
            self._store.popitem(last=False)
        return list(vec)

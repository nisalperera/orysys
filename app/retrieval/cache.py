"""Small LRU cache for query embeddings (RAG stage: embed).

Embedding via a remote API is the slowest step of a search (seconds), and the same question is
often re-asked or re-planned inside one session. Keys are normalised (trim, lowercase, collapsed spaces).
"""
from collections import OrderedDict
from typing import Awaitable, Callable


class CachedEmbedder:
    def __init__(self, fn: Callable[[str], Awaitable[list[float]]], max_size: int = 256):
        self._fn, self._max, self._store = fn, max_size, OrderedDict()
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
        self.misses += 1
        vec = await self._fn(query)
        self._store[key] = list(vec)
        if len(self._store) > self._max:
            self._store.popitem(last=False)
        return vec

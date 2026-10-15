"""Streaming adapter for LangChain chat models. Drops <think>...</think> blocks even when a tag is split across chunks."""
from typing import AsyncIterator


class ThinkStripper:
    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self):
        self.buf = ""
        self.in_think = False

    @staticmethod
    def _partial(buf: str, tag: str) -> int:
        for k in range(min(len(tag) - 1, len(buf)), 0, -1):
            if buf.endswith(tag[:k]):
                return k
        return 0

    def feed(self, text: str) -> str:
        self.buf += text
        out = []
        while True:
            if self.in_think:
                i = self.buf.find(self.CLOSE)
                if i < 0:
                    self.buf = self.buf[-self._partial(self.buf, self.CLOSE):] if self._partial(self.buf, self.CLOSE) else ""
                    break
                self.buf, self.in_think = self.buf[i + len(self.CLOSE):], False
            else:
                i = self.buf.find(self.OPEN)
                if i < 0:
                    k = self._partial(self.buf, self.OPEN)
                    out.append(self.buf[:len(self.buf) - k])
                    self.buf = self.buf[len(self.buf) - k:] if k else ""
                    break
                out.append(self.buf[:i])
                self.buf, self.in_think = self.buf[i + len(self.OPEN):], True
        return "".join(out)

    def flush(self) -> str:
        tail = "" if self.in_think else self.buf
        self.buf = ""
        return tail


def stream_from_langchain(model):
    """model must be created with streaming=True. Returns fn(messages) -> async iterator of visible text."""
    async def fn(messages: list[dict]) -> AsyncIterator[str]:
        strip = ThinkStripper()
        async for chunk in model.astream([(m["role"], m["content"]) for m in messages]):
            content = chunk.content if isinstance(chunk.content, str) else ""
            vis = strip.feed(content)
            if vis:
                yield vis
        tail = strip.flush()
        if tail:
            yield tail

    return fn

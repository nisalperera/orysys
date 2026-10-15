"""Adapter from a LangChain chat model (OpenRouter, vLLM, anything OpenAI compatible) to the engine's LLMFn."""
from app.rlm.jsonutil import strip_think


def from_langchain(model):
    async def fn(messages: list[dict]) -> str:
        resp = await model.ainvoke([(m["role"], m["content"]) for m in messages])
        content = resp.content if isinstance(resp.content, str) else str(resp.content)
        return strip_think(content)

    return fn

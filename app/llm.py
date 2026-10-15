"""LLM factory for the local vLLM server (Qwen3-8B-AWQ).

Qwen3 supports a thinking mode. vLLM accepts it per request through
`chat_template_kwargs.enable_thinking`, which is not part of the OpenAI spec, so it is
sent via `extra_body`. Routing/validation nodes run non-thinking (fast, deterministic);
research and final-answer nodes may enable thinking.
Sampling follows Qwen's recommendations for each mode.
"""
from typing import Any

from app.config import Settings, get_settings

_NON_THINKING = {"temperature": 0.7, "top_p": 0.8, "top_k": 20}
_THINKING = {"temperature": 0.6, "top_p": 0.95, "top_k": 20}


def build_llm_kwargs(s: Settings, thinking: bool = False, temperature: float | None = None) -> dict[str, Any]:
    """Pure function (no network, easy to unit test) that builds ChatOpenAI kwargs."""
    sampling = dict(_THINKING if thinking else _NON_THINKING)
    if temperature is not None:
        sampling["temperature"] = temperature
    return {
        "model": s.llm_model,
        "base_url": s.base_url,
        "api_key": s.api_key,
        "max_tokens": s.llm_max_tokens,
        "timeout": s.llm_timeout_sec,
        "max_retries": s.llm_max_retries,
        "temperature": sampling["temperature"],
        "top_p": sampling["top_p"],
        "extra_body": {
            "top_k": sampling["top_k"],
            "chat_template_kwargs": {"enable_thinking": thinking},
        },
    }


def get_chat_model(thinking: bool = False, temperature: float | None = None, streaming: bool = True):
    from langchain_openai import ChatOpenAI  # lazy import keeps unit tests light

    return ChatOpenAI(streaming=streaming, **build_llm_kwargs(get_settings(), thinking, temperature))


async def llm_healthcheck() -> dict[str, Any]:
    """Used by /health and for graceful degradation when the vLLM server is down."""
    import httpx

    s = get_settings()
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{s.base_url}/models", headers={"Authorization": f"Bearer {s.api_key}"})
            r.raise_for_status()
            ids = [m["id"] for m in r.json().get("data", [])]
            return {"ok": s.llm_model in ids, "served_models": ids}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}

"""LLM factory for any OpenAI-compatible endpoint: OpenRouter (default for this project) or a local vLLM server.

Thinking control is provider specific, so it is chosen from the base URL:
- OpenRouter: `reasoning` object in the request body ({"enabled": true} or {"effort": "none"}).
  Models that cannot disable reasoning still reason, and the engine strips <think> blocks from content.
- vLLM: `chat_template_kwargs.enable_thinking`.
Routing, validation and sub-agent nodes run non-thinking (fast, deterministic). Research reduce and final
answer may use thinking. Sampling follows Qwen's recommendations for each mode.
"""
from typing import Any

_NON_THINKING = {"temperature": 0.7, "top_p": 0.8, "top_k": 20}
_THINKING = {"temperature": 0.6, "top_p": 0.95, "top_k": 20}


def is_openrouter(base_url: str) -> bool:
    return "openrouter.ai" in (base_url or "")


def build_llm_kwargs(s: Any, thinking: bool = False, temperature: float | None = None) -> dict[str, Any]:
    """Pure function (no network, no config import) so it is trivial to unit test."""
    sampling = dict(_THINKING if thinking else _NON_THINKING)
    if temperature is not None:
        sampling["temperature"] = temperature
    extra: dict[str, Any] = {"top_k": sampling["top_k"]}
    if is_openrouter(s.base_url):
        extra["reasoning"] = {"enabled": True} if thinking else {"effort": "none"}
    else:
        extra["chat_template_kwargs"] = {"enable_thinking": thinking}
    return {
        "model": s.llm_model,
        "base_url": s.base_url,
        "api_key": s.api_key,
        "max_tokens": s.llm_max_tokens,
        "timeout": s.llm_timeout_sec,
        "max_retries": s.llm_max_retries,
        "temperature": sampling["temperature"],
        "top_p": sampling["top_p"],
        "extra_body": extra,
    }


def get_chat_model(thinking: bool = False, temperature: float | None = None, streaming: bool = True):
    from langchain_openai import ChatOpenAI  # lazy import keeps unit tests light

    from app.config import get_settings

    return ChatOpenAI(streaming=streaming, **build_llm_kwargs(get_settings(), thinking, temperature))


async def llm_healthcheck() -> dict[str, Any]:
    """Is the configured model id served by the endpoint? Used by /health and the demo preflight."""
    import httpx

    from app.config import get_settings

    s = get_settings()
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get(f"{s.base_url.rstrip('/')}/models", headers={"Authorization": f"Bearer {s.api_key}"})
            r.raise_for_status()
            ids = [m.get("id") for m in r.json().get("data", [])]
            return {"ok": s.llm_model in ids, "model": s.llm_model, "base_url": s.base_url, "models_listed": len(ids)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "model": s.llm_model, "base_url": s.base_url, "error": str(exc)[:200]}


async def ensure_llm_ready() -> None:
    """Fail fast with an actionable message instead of burning requests on a wrong model id or key."""
    h = await llm_healthcheck()
    if not h["ok"]:
        raise RuntimeError(
            f"LLM not ready: model '{h['model']}' at {h['base_url']} "
            f"({h.get('error') or 'model id not listed by the endpoint'}). "
            "Check BASE_URL, API_KEY and LLM_MODEL in .env (run: python -m scripts.check_env).")

from types import SimpleNamespace
import pytest
from app.rlm.executor import RLMEngine, LLMCallError


@pytest.mark.asyncio
async def test_permanent_provider_error_is_not_retried():
    calls = 0
    class BadCredentials(Exception):
        status_code = 401
    async def llm(messages):
        nonlocal calls
        calls += 1
        raise BadCredentials("private-provider-marker")
    config = SimpleNamespace(llm_retries=2, llm_timeout_sec=1, retry_backoff_sec=0)
    engine = RLMEngine(llm, None, None, config=config)
    with pytest.raises(LLMCallError) as error:
        await engine._call_llm([])
    assert calls == 1
    assert "private-provider-marker" not in str(error.value)


@pytest.mark.asyncio
async def test_transient_provider_error_is_retried():
    calls = 0
    async def llm(messages):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("temporary")
        return "ok"
    config = SimpleNamespace(llm_retries=2, llm_timeout_sec=1, retry_backoff_sec=0)
    engine = RLMEngine(llm, None, None, config=config)
    assert await engine._call_llm([]) == "ok"
    assert calls == 2

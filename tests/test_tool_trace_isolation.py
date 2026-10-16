import pytest
import app.trace_safety as tracing


class MonitoringError(Exception):
    pass

MonitoringError.__module__ = "langsmith.errors"


@pytest.mark.asyncio
@pytest.mark.parametrize("when", ["before", "after"])
async def test_monitoring_failure_does_not_repeat_tool(monkeypatch, when):
    calls = 0
    def broken_trace(**options):
        def decorate(function):
            async def wrapped(*args, **kwargs):
                if when == "before":
                    raise MonitoringError("private-monitoring-detail")
                await function(*args, **kwargs)
                raise MonitoringError("private-monitoring-detail")
            return wrapped
        return decorate
    monkeypatch.setattr(tracing, "traceable", broken_trace)
    @tracing.safe_traceable(name="test_tool", run_type="tool")
    async def tool():
        nonlocal calls
        calls += 1
        return {"ok": True}
    assert await tool() == {"ok": True}
    assert calls == 1

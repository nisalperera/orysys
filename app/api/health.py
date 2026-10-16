"""Bounded public health response; detailed provider diagnostics stay internal."""
import asyncio
import logging

log = logging.getLogger("api.health")


async def public_healthcheck(check):
    try:
        result = await asyncio.wait_for(check(), timeout=10.0)
        ok = result.get("ok") is True
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.warning("provider health check failed: %s", type(exc).__name__)
        ok = False
    if ok:
        return {"status": "ok", "llm": {"ok": True}}
    return {
        "status": "degraded",
        "llm": {"ok": False, "code": "provider_unavailable"},
    }

"""Failure-isolated async tracing; never retry a completed side-effecting handler."""
import logging
from functools import wraps
from app.observability import traceable

log = logging.getLogger("tracing")


def safe_traceable(**options):
    def decorate(function):
        @wraps(function)
        async def wrapped(*args, **kwargs):
            started = False
            completed = False
            result = None

            async def invoke():
                nonlocal started, completed, result
                started = True
                result = await function(*args, **kwargs)
                completed = True
                return result

            try:
                traced = traceable(**options)(invoke)
                return await traced()
            except Exception as exc:
                if not type(exc).__module__.startswith("langsmith"):
                    raise
                log.warning("Tracing unavailable: %s", type(exc).__name__)
                if completed:
                    return result
                if not started:
                    return await function(*args, **kwargs)
                # A handler that started but did not finish must not be repeated.
                raise
        return wrapped
    return decorate

"""All handlers are async. Identity is server-owned, never accepted in tool arguments.
Authorization happens BEFORE parameter validation and execution. No eval/exec/shell tools.
"""
import asyncio
import logging
from dataclasses import dataclass
from pydantic import BaseModel
from app.trace_safety import safe_traceable

log = logging.getLogger("tools")
class ToolError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code

@dataclass(frozen=True)
class Spec:
    name: str
    schema: type[BaseModel]
    roles: frozenset[str]
    handler: object
    timeout: float = 15

class Registry:
    def __init__(self, users):
        self.users, self.specs = users, {}

    def register(self, spec):
        if spec.name in self.specs:
            raise ValueError("duplicate tool")
        self.specs[spec.name] = spec

    @safe_traceable(
        name="authorized_tool", run_type="tool",
        process_inputs=lambda values: {"payload": "redacted"},
        process_outputs=lambda values: {"payload": "redacted"},
    )
    async def execute(self, user_id, name, arguments, emit=None):
        user = self.users.get(user_id)
        spec = self.specs.get(name)
        role = getattr(getattr(user, "role", None), "value", None)
        if user is None or spec is None or role not in spec.roles:
            log.warning("tool denied", extra={"extra_fields": {"user_id": user_id, "tool": name}})
            if emit: emit("tool_denied", tool=name)
            raise ToolError("forbidden", "Your role cannot execute this tool.")
        try:
            params = spec.schema.model_validate(arguments)
        except Exception as exc:
            raise ToolError("invalid_parameters", "Invalid tool parameters.") from exc
        if emit: emit("tool_call", tool=name, status="started")
        log.info("tool started", extra={"extra_fields": {"user_id": user_id, "tool": name}})
        try:
            result = await asyncio.wait_for(spec.handler(user, params), spec.timeout)
        except asyncio.TimeoutError as exc:
            if emit: emit("tool_call", tool=name, status="timeout")
            raise ToolError("timeout", "Tool timed out. Please retry.") from exc
        except asyncio.CancelledError:
            raise
        except ToolError:
            raise
        except Exception as exc:
            log.exception("tool failed: %s", name)
            if emit: emit("tool_call", tool=name, status="failed")
            raise ToolError("unavailable", "Tool service is temporarily unavailable.") from exc
        if emit: emit("tool_call", tool=name, status="completed")
        log.info("tool completed", extra={"extra_fields": {"user_id": user_id, "tool": name}})
        return result

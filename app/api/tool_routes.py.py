"""Install once after FastAPI creation. Limits are checked before streaming headers are sent.
Use one worker for this POC; Redis is required for shared multi-worker buckets.
"""
import os
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from app.auth.dependencies import authenticate_token
from app.security.token_bucket import TokenBucket
from app.tools.registry import ToolError

class ToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=60)
    arguments: dict = Field(default_factory=dict)

def install(app):
    bucket = TokenBucket(int(os.getenv("RATE_LIMIT_CAPACITY", "10")),
                         float(os.getenv("RATE_LIMIT_REFILL_PER_SEC", "0.5")))

    @app.middleware("http")
    async def limits(request: Request, call_next):
        if request.method == "POST" and request.url.path in {"/chat", "/chat/stream", "/tools/execute"}:
            user = authenticate_token(request.headers.get("x-api-key", ""))
            if user is None:
                return JSONResponse({"detail": "invalid or missing API key"}, status_code=401)
            ok, wait = bucket.consume(user.user_id)
            if not ok:
                return JSONResponse({"detail": "Rate limit exceeded. Please retry later.", "retry_after": wait},
                                    status_code=429, headers={"Retry-After": str(wait)})
        return await call_next(request)

    @app.post("/tools/execute")
    async def execute(body: ToolRequest, request: Request):
        user = authenticate_token(request.headers.get("x-api-key", ""))
        if user is None:
            raise HTTPException(401, "invalid or missing API key")
        tools = getattr(request.app.state.service.deps, "tools", None)
        if tools is None:
            raise HTTPException(503, "Tool registry not configured")
        try:
            result = await tools.registry.execute(user.user_id, body.name, body.arguments)
            return result.model_dump(mode="json") if hasattr(result, "model_dump") else result
        except ToolError as exc:
            raise HTTPException({"forbidden": 403, "invalid_parameters": 422, "timeout": 504}.get(exc.code, 503),
                                detail={"code": exc.code, "message": str(exc)}) from exc

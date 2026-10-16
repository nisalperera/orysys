"""FastAPI app: async endpoints, SSE streaming, auth, request ids, structured logging, safe error handling.

Run:  uvicorn app.api.main:app --port 8080
Try:  curl -N -X POST localhost:8080/chat/stream -H 'X-API-Key: dev-analyst-key' -H 'Content-Type: application/json' \
        -d '{"message": "What is the runbook for connection pool saturation?"}'
"""
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.api.sse import sse_iter
from app.api.tool_routes import install
from app.auth.dependencies import authenticate_token
from app.logging_config import log_event, request_id_var, setup_logging

log = logging.getLogger("api")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_\-]{8,64}$")


async def current_user(x_api_key: str | None = Header(default=None)):
    user = authenticate_token(x_api_key or "")
    if user is None:
        raise HTTPException(status_code=401, detail="invalid or missing API key")
    return user


def create_app(service_builder=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        setup_logging()
        if service_builder is not None:
            app.state.service = await service_builder()
        else:
            from app.api.wiring import build_service
            app.state.service = await build_service()
        yield

    app = FastAPI(title="Lanka Meridian Bank AI Assistant", version="0.2.0", lifespan=lifespan)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        token, t0 = request_id_var.set(rid), time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001
            log.exception("unhandled error")
            response = JSONResponse({"error": "internal_error", "request_id": rid}, status_code=500)
        response.headers["X-Request-Id"] = rid
        log_event(log, "request", method=request.method, path=request.url.path, status=response.status_code,
                  ms=int((time.perf_counter() - t0) * 1000))
        request_id_var.reset(token)
        return response

    @app.get("/health")
    async def health(request: Request):
        info = {"status": "ok"}
        try:
            from app.llm import llm_healthcheck
            info["llm"] = await llm_healthcheck()
            info["status"] = "ok" if info["llm"].get("ok") else "degraded"
        except Exception as exc:  # noqa: BLE001
            info.update(status="degraded", llm={"ok": False, "error": str(exc)[:120]})
        return info

    @app.post("/chat/stream")
    async def chat_stream(body: ChatRequest, request: Request, user=Depends(current_user)):
        session_id = body.session_id or uuid.uuid4().hex
        service = request.app.state.service
        try:
            service.check_session(user, session_id)
        except PermissionError:
            raise HTTPException(status_code=403, detail="session belongs to another user")
        return StreamingResponse(
            sse_iter(service.stream(user, session_id, body.message)), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "X-Session-Id": session_id})

    @app.post("/chat")
    async def chat(body: ChatRequest, request: Request, user=Depends(current_user)):
        session_id = body.session_id or uuid.uuid4().hex
        service = request.app.state.service
        try:
            final = await service.ask(user, session_id, body.message)
        except PermissionError:
            raise HTTPException(status_code=403, detail="session belongs to another user")
        return {"session_id": session_id, **final}

    from app.api.tool_routes import install
    install(app)

    return app


app = create_app()

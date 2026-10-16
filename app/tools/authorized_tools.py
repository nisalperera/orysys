"""Knowledge and research wrappers share the same server-owned registry as the tools API.
RAG affected stage: retrieve. Existing metadata filters remain intact.
The enterprise adapter is MOCK DATA, not an MCP transport. No arbitrary Python execution.
"""
from pydantic import BaseModel, ConfigDict, Field
from app.auth.models import USERS
from app.trace_safety import safe_traceable
from app.retrieval.schemas import SearchRequest
from app.tools.registry import Registry, Spec, ToolError

ALL = frozenset({"viewer", "analyst", "admin"})
ANALYST = frozenset({"analyst", "admin"})

class StrictArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

class ResearchArgs(StrictArgs):
    question: str = Field(min_length=2, max_length=2000)

class CatalogArgs(StrictArgs):
    service: str = Field(min_length=2, max_length=80, pattern=r"^[a-zA-Z0-9 _-]+$")

class EmptyArgs(StrictArgs):
    pass

# Synthetic service records only, intentionally no employee PII or operational secrets.
SERVICES = {
    "payments-api": {"service": "payments-api", "owner": "Payments Platform", "on_call": "platform lead"},
    "settlement-svc": {"service": "settlement-svc", "owner": "Payments Platform", "vendor": "NovaPay"},
    "card-switch-gw": {"service": "card-switch-gw", "owner": "Cards Platform"},
}

class AuthorizedTools:
    def __init__(self, retriever, engine_factory, emit=None, timeout=25, research_timeout=150):
        self.raw_retriever, self.engine_factory = retriever, engine_factory
        self.emit = emit
        self.registry = Registry(USERS)
        self.registry.register(Spec("knowledge_search", SearchRequest, ALL, self._search, timeout))
        self.registry.register(Spec("python_analysis", ResearchArgs, ANALYST, self._research, research_timeout))
        self.registry.register(Spec("service_catalog", CatalogArgs, ANALYST, self._catalog, timeout))
        self.registry.register(Spec("admin_diagnostics", EmptyArgs, frozenset({"admin"}), self._diagnostics, timeout))

    @classmethod
    def from_settings(cls, retriever, engine_factory, settings, emit=None):
        return cls(
            retriever, engine_factory, emit=emit,
            timeout=settings.tool_timeout_sec,
        )

    @safe_traceable(
        name="authorized_hybrid_search", run_type="retriever",
        process_inputs=lambda values: {"payload": "redacted"},
        process_outputs=lambda values: {"payload": "redacted"},
    )
    async def _search(self, user, params):
        return await self.raw_retriever.search(user, params)

    async def _research(self, user, params):
        # Existing RLM uses allowlisted Python plan primitives, not arbitrary exec.
        # RLM counts and aggregates findings with the existing python_analysis module.
        engine = self.engine_factory(self.emit or (lambda ev: None))
        return await engine.run(user, params.question)

    async def _catalog(self, user, params):
        record = SERVICES.get(params.service.lower())
        return {"source": "mock_enterprise_adapter", "mock": True, "record": record}

    async def _diagnostics(self, user, params):
        return {"mock": True, "status": "ok", "tools": sorted(self.registry.specs)}

    async def search(self, user, req):
        return await self.registry.execute(user.user_id, "knowledge_search", req.model_dump())

    async def run(self, user, question):
        return await self.registry.execute(
            user.user_id, "python_analysis", {"question": question},
            emit=(lambda kind, **data: self.emit({"type": kind, **data})) if self.emit else None)

    def embed_query(self, query):
        return self.raw_retriever.embed_query(query)

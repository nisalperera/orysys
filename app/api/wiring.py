"""Production wiring: LLM, Pinecone, authorized tools, RLM, LangGraph and chat service."""
import asyncio
import logging

from app.api.service import ChatService
from app.auth.models import USERS
from app.config import get_settings
from app.graph.builder import build_graph
from app.graph.deps import Deps
from app.graph.llm_stream import stream_from_langchain
from app.llm import get_chat_model
from app.retrieval.factory import build_retriever
from app.rlm.catalog import Catalog
from app.rlm.executor import RLMEngine
from app.rlm.llm_adapter import from_langchain
from app.rlm.models import RLMConfig
from app.tools.authorized_tools import AuthorizedTools

log = logging.getLogger("wiring")


async def build_service() -> ChatService:
    settings = get_settings()

    retriever = build_retriever()
    catalog = Catalog.from_dir(settings.docs_dir)

    llm = from_langchain(
        get_chat_model(thinking=False, streaming=False)
    )
    llm_stream = stream_from_langchain(
        get_chat_model(thinking=False, streaming=True)
    )

    def raw_engine(emit):
        # This function is called after guarded has been initialized.
        # RLM sub-agent searches must also pass registry authorization.
        return RLMEngine(
            llm,
            guarded,
            catalog,
            RLMConfig(),
            emit=emit,
        )

    # Shared registry for standard retrieval and the tools API.
    guarded = AuthorizedTools(retriever, raw_engine)

    def make_engine(emit):
        # Per-request wrapper prevents concurrent research requests
        # from sharing their event callbacks.
        return AuthorizedTools(
            retriever,
            raw_engine,
            emit=emit,
        )

    deps = Deps(
        users=USERS,
        llm=llm,
        llm_stream=llm_stream,
        search=guarded.search,
        make_engine=make_engine,
        departments=lambda user: set(
            catalog.stats(user)["by_department"]
        ),
        bank_name=settings.bank_name,
    )

    # /tools/execute retrieves its registry from this attribute.
    deps.tools = guarded

    service = ChatService(build_graph(deps), deps)

    log.info(
        "tool registry ready",
        extra={
            "extra_fields": {
                "tools": sorted(guarded.registry.specs),
            }
        },
    )

    try:
        await asyncio.wait_for(
            retriever.embed_query("warm up"),
            timeout=30,
        )
        log.info("embedding warm-up done")
    except Exception as exc:
        log.warning("embedding warm-up failed: %s", exc)

    return service

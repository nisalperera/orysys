"""Production wiring: real LLM (OpenRouter or vLLM), Pinecone retriever, RLM engine, LangGraph, chat service."""
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

log = logging.getLogger("wiring")


async def build_service() -> ChatService:
    s = get_settings()
    retriever = build_retriever()
    catalog = Catalog.from_dir(s.docs_dir)
    llm = from_langchain(get_chat_model(thinking=False, streaming=False))
    llm_stream = stream_from_langchain(get_chat_model(thinking=False, streaming=True))

    def make_engine(emit):
        return RLMEngine(llm, retriever, catalog, RLMConfig(), emit=emit)

    deps = Deps(users=USERS, llm=llm, llm_stream=llm_stream, search=retriever.search, make_engine=make_engine,
                departments=lambda u: set(catalog.stats(u)["by_department"]), bank_name=s.bank_name)
    service = ChatService(build_graph(deps), deps)
    try:  # warm the embedding endpoint so the first user question is not the slow one
        await asyncio.wait_for(retriever.embed_query("warm up"), timeout=30)
        log.info("embedding warm-up done")
    except Exception as exc:  # noqa: BLE001
        log.warning("embedding warm-up failed: %s", exc)
    return service

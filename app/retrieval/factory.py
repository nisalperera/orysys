"""
Wires HybridRetriever to Pinecone, BM25 params and the project's embed_query (provider agnostic).
"""
import logging
from functools import lru_cache

from app.retrieval.cache import CachedEmbedder
from app.retrieval.hybrid import HybridRetriever

log = logging.getLogger("retrieval")
NAMESPACES = ("incident", "runbook", "architecture", "product_spec", "meeting_notes", "policy")


@lru_cache
def build_retriever() -> HybridRetriever:
    from pinecone import Pinecone
    from pinecone_text.sparse import BM25Encoder

    from app.config import get_settings
    from app.retrieval.embeddings import embed_query

    s = get_settings()
    index = Pinecone(api_key=s.pinecone_api_key).Index(s.pinecone_index)
    sparse_fn = None
    try:
        sparse_fn = BM25Encoder().load(s.bm25_params_path).encode_queries
    except Exception as exc:  # noqa: BLE001
        log.warning("BM25 params not loaded (%s), running dense only", exc)
    return HybridRetriever(
        index, CachedEmbedder(embed_query, getattr(s, "embedding_cache_size", 256)), sparse_fn, NAMESPACES,
        default_alpha=s.hybrid_alpha,
        min_score=getattr(s, "retrieval_min_score", 0.30),
        max_per_doc=getattr(s, "retrieval_max_per_doc", 2),
    )

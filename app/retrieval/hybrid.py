"""Async hybrid retrieval over Pinecone (RAG stages: retrieve, plus a light post-filter).

Scoring: dense vector scaled by alpha, sparse (BM25) values by (1 - alpha). On a dotproduct index
Pinecone returns alpha * dense_score + (1 - alpha) * sparse_score in one query per namespace.

Post-processing order (each step is reported in RetrievalResult for the activity panel):
  1. access_level re-check (defence in depth)
  2. relevance floor `min_score`  -> weak matches are dropped, `no_relevant_results` is set if nothing is left
  3. per-document cap `max_per_doc` -> one long incident cannot fill the whole context
  4. top_k cut

Targeted retrieval: when the caller passes `doc_ids` (the RLM sub-agents do), the caller has already chosen
the documents, so the relevance floor and the per-document cap are switched off. Otherwise the cap would
throw away exactly the sections the sub-agent asked for. Access control still applies in full.

Resilience: per-namespace timeout and partial results, dense-only fallback, RetrievalError when nothing works.
Dependencies are injected so the class is testable without Pinecone or an LLM provider.
"""
import asyncio
import logging
import time
from collections import Counter
from typing import Any, Awaitable, Callable, Optional

from app.auth.models import User
from app.retrieval.filters import build_filter, namespaces_for
from app.retrieval.schemas import Hit, RetrievalResult, SearchRequest

log = logging.getLogger("retrieval")

EmbedFn = Callable[[str], Awaitable[list[float]]]
SparseFn = Callable[[str], dict]


class RetrievalError(Exception):
    """Raised when retrieval cannot produce any result (not for partial failures)."""


def _get(obj: Any, key: str, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def scale_hybrid(dense: list[float], sparse: Optional[dict], alpha: float) -> tuple[list[float], Optional[dict]]:
    if not sparse or not sparse.get("indices"):
        return dense, None
    return (
        [v * alpha for v in dense],
        {"indices": list(sparse["indices"]), "values": [v * (1 - alpha) for v in sparse["values"]]},
    )


def apply_post_filters(hits: list[Hit], allowed_levels: set[str], min_score: float, max_per_doc: int,
                       top_k: int) -> tuple[list[Hit], int, int, int]:
    """Returns (final_hits, leaked, below_min_score, doc_cap_dropped). Pure and unit tested."""
    ordered = sorted(hits, key=lambda h: h.score, reverse=True)
    allowed = [h for h in ordered if h.access_level in allowed_levels]
    leaked = len(ordered) - len(allowed)
    relevant = [h for h in allowed if h.score >= min_score]
    below = len(allowed) - len(relevant)
    per_doc: Counter = Counter()
    capped: list[Hit] = []
    for h in relevant:
        if max_per_doc and per_doc[h.doc_id] >= max_per_doc:
            continue
        per_doc[h.doc_id] += 1
        capped.append(h)
    return capped[:top_k], leaked, below, len(relevant) - len(capped)


class HybridRetriever:
    def __init__(self, index: Any, embed_query: EmbedFn, sparse_encode: Optional[SparseFn],
                 namespaces: tuple[str, ...], default_alpha: float = 0.6, namespace_timeout_sec: float = 8.0,
                 min_score: float = 0.0, max_per_doc: int = 0):
        self.index, self.embed_query, self.sparse_encode = index, embed_query, sparse_encode
        self.namespaces, self.default_alpha, self.timeout = namespaces, default_alpha, namespace_timeout_sec
        self.min_score, self.max_per_doc = min_score, max_per_doc

    async def search(self, user: User, req: SearchRequest) -> RetrievalResult:
        started = time.perf_counter()
        alpha = self.default_alpha if req.alpha is None else req.alpha
        reasons: list[str] = []

        targeted = bool(req.doc_ids)  # caller already chose the documents (RLM sub-agents)
        min_score = 0.0 if targeted else self.min_score
        max_per_doc = 0 if targeted else self.max_per_doc

        t0 = time.perf_counter()
        try:
            dense = await self.embed_query(req.query)
        except Exception as exc:  # noqa: BLE001
            log.error("embedding failed: %s", exc)
            raise RetrievalError(f"Embedding service unavailable: {exc}") from exc
        embed_ms = int((time.perf_counter() - t0) * 1000)

        sparse = None
        if self.sparse_encode is None:
            reasons.append("sparse encoder not loaded, dense only")
        else:
            try:
                sparse = self.sparse_encode(req.query)
            except Exception as exc:  # noqa: BLE001
                reasons.append(f"sparse encoder failed, dense only: {exc}")
        qd, qs = scale_hybrid(dense, sparse, alpha)

        flt = build_filter(user, req)
        targets = namespaces_for(req, self.namespaces)
        base = dict(alpha=alpha, applied_filter=flt, min_score=min_score, embed_ms=embed_ms)
        if not targets:
            return RetrievalResult(hits=[], namespaces_searched=[], **base)

        fetch_k = min(req.top_k * 2, 40) if max_per_doc else req.top_k  # over-fetch so the cap still fills top_k
        t1 = time.perf_counter()
        outcomes = await asyncio.gather(
            *(self._query_ns(ns, qd, qs, flt, fetch_k) for ns in targets), return_exceptions=True)
        query_ms = int((time.perf_counter() - t1) * 1000)

        raw: list[Hit] = []
        failed: list[str] = []
        for ns, out in zip(targets, outcomes):
            if isinstance(out, Exception):
                failed.append(ns)
                reasons.append(f"namespace '{ns}' failed: {type(out).__name__}")
                log.warning("namespace %s failed: %s", ns, out)
            else:
                raw.extend(out)
        if len(failed) == len(targets):
            raise RetrievalError("Vector database unavailable for all namespaces")

        hits, leaked, below, capped = apply_post_filters(
            raw, set(user.access_levels), min_score, max_per_doc, req.top_k)
        if leaked:
            log.error("access filter leak blocked: %d hits dropped", leaked)

        return RetrievalResult(
            hits=hits,
            namespaces_searched=[n for n in targets if n not in failed],
            failed_namespaces=failed,
            degraded=bool(reasons) or bool(failed),
            degraded_reasons=reasons,
            no_relevant_results=(not hits and (below > 0 or not raw)),
            dropped_below_min_score=below,
            dropped_by_doc_cap=capped,
            query_ms=query_ms,
            latency_ms=int((time.perf_counter() - started) * 1000),
            **base,
        )

    async def _query_ns(self, ns: str, dense: list[float], sparse: Optional[dict], flt: dict, top_k: int) -> list[Hit]:
        def _call():
            kw = dict(vector=dense, top_k=top_k, namespace=ns, filter=flt, include_metadata=True)
            if sparse:
                kw["sparse_vector"] = sparse
            return self.index.query(**kw)

        res = await asyncio.wait_for(asyncio.to_thread(_call), timeout=self.timeout)
        out: list[Hit] = []
        for m in _get(res, "matches", []) or []:
            md = _get(m, "metadata", {}) or {}
            try:
                out.append(Hit(
                    chunk_id=_get(m, "id"), doc_id=md["doc_id"], title=md["title"], section=md.get("section", ""),
                    document_type=md["document_type"], department=md["department"],
                    access_level=md["access_level"], created_date=md["created_date"],
                    score=float(_get(m, "score", 0.0)), text=md.get("text", "")))
            except KeyError as exc:
                log.warning("skipping malformed match %s: missing %s", _get(m, "id"), exc)
        return out

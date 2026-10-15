# T1: Hybrid retrieval (RAG stage: retrieve)

Files: `app/auth/models.py`, `app/retrieval/{schemas,filters,hybrid,factory}.py`, `scripts/search_demo.py`, `tests/test_retrieval.py`.

- Score = alpha * dense + (1 - alpha) * sparse, computed by Pinecone in one dotproduct query per namespace. `HYBRID_ALPHA` sets the default, a request can override it.
- Namespace = document_type. Queries fan out concurrently with `asyncio.gather` and merge by score.
- RBAC: the access_level filter comes from the user's role on the server. Request filters only narrow. Every hit is re-checked after retrieval.
- Failures: a failed namespace is reported and the rest return. No sparse encoder means dense only. Embedding or total vector DB failure raises `RetrievalError`.
- `SearchRequest` is the validated parameter schema reused by the `knowledge_search` tool in T4.

Run: `PYTHONPATH=. pytest -q tests/test_retrieval.py` and `python -m scripts.search_demo viewer1 "payment pool exhaustion"`.

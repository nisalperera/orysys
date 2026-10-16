# T4 implementation and honest scope

## Included
- Registry checks server-owned user identity and role before validation/execution.
- Knowledge search: Viewer, Analyst, Admin. Existing Pinecone metadata filters preserved.
- Python analysis/research: Analyst and Admin. Wrapper calls existing RLM and deterministic Python analysis;
  model cannot supply executable code or choose credentials. Sub-agent retrieval also passes the registry.
- Mock service catalog: Analyst/Admin only. Admin diagnostics: Admin only, read-only synthetic response.
- Async timeouts, safe client errors, structured logs. Research tool status forwarded to RLM activity events.
- Per-user token bucket applied before streaming headers for /chat, /chat/stream and /tools/execute.
  Capacity 10, refill 0.5 requests/sec. 429 with Retry-After. One worker only; in-memory state resets on restart.

## Not included / not claimed
- Actual MCP server or MCP transport. Service catalog is a marked mock enterprise-data adapter.
- Autonomous graph selection of service_catalog or admin_diagnostics: invoke through /tools/execute for now.
- Human approval / LangGraph interrupt: deferred bonus. All current tools are read-only.
- Full security hardening: existing injection regexes are heuristic, not a security boundary.
- Existing output validator is not full semantic entailment validation. Its citation and number checks cannot prove correctness.
- Existing token streaming can expose provisional content before final validation; this patch does not solve that.

## Install
Copy the patch's contents into repository root. Run python -m scripts.apply_t4.
The installer validates all anchors before writes and saves .py.t4.bak backups. Review the diff.
No push/deployment or remote state changes are performed.

## Config
RATE_LIMIT_CAPACITY=10
RATE_LIMIT_REFILL_PER_SEC=0.5
These environment variables are already in the original .env.example. They are read at app construction.
Use uvicorn app.api.main:app --port 8000 --workers 1.

## Verify
PYTHONPATH=. pytest -q tests
Test viewer versus analyst service_catalog requests with X-API-Key authentication.
Viewer gets 403; analyst gets mock=true and service metadata. Viewer admin_diagnostics gets 403;
admin gets a read-only tool list. Use a small capacity in a temporary server process to verify 429.
Retest the existing viewer question and analyst research demo.

## RAG impact
Only retrieve is wrapped by registry authorization. Chunk, embed, store, ranking and existing access filters
are unchanged. The existing RLM generation and deterministic analytics are reused, not replaced.

# T6: Offline failure drills and submission hardening

## Run

    python -m scripts.install_t6_docs
    PYTHONPATH=. pytest -q tests
    python -m scripts.run_failure_drills

Needs the real FastAPI and LangGraph dependencies plus the earlier tests/graph_helpers.py.
No live backend is required. No external API resources are disabled, deleted, or modified.
Tests use create_app(service_builder=...) and a real compiled LangGraph with fake LLM/retrieval/research.
Tracing is disabled; demo credentials are set only inside tests. Use localhost for actual deployment.

## Coverage
- Vector DB unavailable: honest no-search response, no fake evidence.
- Retrieval timeout: bounded response using configured dependency timeout.
- Response LLM failure: extractive fallback with citations and degraded flag.
- Supervisor LLM failure: heuristic routing.
- RLM failure: standard-search fallback with user-facing limitation.
- Missing/invalid identity and invalid request bodies: 401/422 before model execution.
- Session ownership: another authenticated user cannot read the same conversation.
- Per-user bucket: 429 before SSE headers; another user retains independent capacity.
- Tool roles: Viewer denied, model/body role field cannot escalate authority.
- Enterprise adapter outage/timeout: 503/504 with safe error details.
- Whole-turn timeout: generic apology, not an incomplete draft.
- Client disconnect: service iterator cleanup and bus removal (not a real TCP/proxy test).

No real MCP transport is tested: enterprise_probe is a registered fake handler.
This suite tests deterministic injected faults, not real provider compatibility or rate-limit headers from OpenRouter.
It does not establish full security. Regex guards and citation checks have documented limits.

## Reports
failure-drill-results/<timestamp>/pytest.log, junit.xml, summary.json.
Runner exits nonzero for failures, collection errors, skipped drills or no collected drills.
A skipped integration suite is not a successful verification. Reports are local/private; keep them out of git.

## Manual submission checklist
- Run the full API acceptance suite again after fixing any failures.
- Browser: role change clears history; fresh session; sources expand; activity visible; provisional tokens labelled.
- LangSmith: normal and research trace trees, thread grouping, no credentials in screenshots.
- Fresh clone: install requirements in a clean venv and follow README exactly.
- BM25 params are not committed: document how to regenerate them and that a missing encoder is dense-only/degraded.
- Confirm query embedding model equals the model used for ingestion; dimensions alone do not prove compatibility.
- Check git diff and tracked files for .env, API keys, backup files, report logs and credentials before making repo public.
- Ensure README/config_guide agree on API entry point, UI command, auth, rate limits and provider settings.
- Limit POC to one API worker: buckets/checkpoints are process-local and reset on restart.
- Document mock MCP data, lack of autonomous enterprise-tool selection, no HITL, no long-term persistence.
- Do not claim provisional streaming is output-leak prevention.
- Record a short demo only if that satisfies the evaluator: the brief literally says 45 minutes, do not assume a typo.
- Verify repository/video links from a logged-out browser; keep commit history; submit before the deadline.

## Verified during authoring
Three report-parser unit tests passed. All delivered Python sources compile.
The integration drills are NOT executed in the authoring sandbox (FastAPI/LangGraph are absent).
Run them locally; do not claim they passed until the report says complete=true.

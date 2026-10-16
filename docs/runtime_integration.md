# Runtime integration and configuration

## Scope

This update targets a49bf46796073a763285d6b8a7b32eab53178a3f.
It does not change ports, corpus, embedding models in your real environment,
index contents, CI pipelines, cloud resources or remote repository state.

## Final validation

API final results and terminal validation activity expose:

- `ok`: validation status of the original model draft.
- `final_ok`: validation status of the selected sanitized or safe replacement text.
- `action`: passed, sanitized or replaced.
- `issues`: findings from validation of the original draft.

Policy notes appended by the server are not revalidated by this update.
`final_ok` does not prove semantic entailment of every sentence.

## Health

GET /health retains HTTP 200 with a status body for compatibility:

    {"status": "degraded", "llm": {"ok": false, "code": "provider_unavailable"}}

The public endpoint excludes model IDs, provider URLs and raw exceptions.
The internal llm_healthcheck helper remains available to local diagnostic tools.
The wrapper bounds its check to 10 seconds and preserves cancellation.
The model-list check does not prove successful chat generation or embeddings.
Container liveness still uses /openapi.json, not repeated provider checks.

## Retrieval activity and tracing

Public degradation reasons are translated into a fixed set of safe messages.
Unknown reasons become generic incomplete-retrieval messages.
Sparse-encoder exception text is removed from returned retrieval metadata.

The outer graph retrieval span now uses the existing safe tracing wrapper.
Monitoring failures after a completed search return the completed result rather
than rerunning the search. Real span parentage/delivery still need verification.

RAG stages: retrieve and generate/validate. No chunk/embed/store changes or
learned reranker are introduced.

## Timeout configuration

TOOL_TIMEOUT_SEC now configures knowledge_search, service_catalog and
admin_diagnostics through the production configured-tools factory.
Research retains its separate 150-second registry default.

The chat turn timeout now includes waiting for the per-session lock, not just
graph execution. Queue timeout uses the existing safe degraded failure payload;
it does not cancel the other request holding that lock.

## Provider configuration

.env.example is an EDIT-BEFORE-USE template for a single hosted endpoint
supporting both selected chat and embedding models. The model identifiers are
intentional placeholders, and embedding dimensions must match the existing
index. It is not a ready-to-run credential/model configuration.

Do not copy it over your working .env. No new embedding endpoint variable exists.
For local deployment, a gateway or equivalent endpoint must serve both required
APIs with the current shared BASE_URL. An ordinary chat-only vLLM server does
not satisfy that assumption. Docker host-model addresses must use a reachable
host address; container localhost is not the host machine.

API: 8000. Streamlit: 3000. Compose UI backend: http://api:8000.
LANGSMITH_PROJECT documents the trace project; choose the correct regional endpoint.

## Validation

Run the full suite, failure drills, Compose validation and image builds after merging.
Previous passing tests predate this update.

MCP server/client integration and request-scoped tool activity plumbing are
not included. Existing generic trace spans still need live demo verification.

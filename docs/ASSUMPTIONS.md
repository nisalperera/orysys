# Assumptions, limitations and trade-offs

## Scope and data

- Lanka Meridian Bank is fictional. The corpus and enterprise service records are synthetic.
- The assessment is a POC demonstrating explainable orchestration, retrieval,
  controlled tools, observability and safe degradation, not a production banking system.
- Documents are generated deterministically. Do not regenerate the corpus or recreate
  the Pinecone index during normal startup.

## Access control

- Viewer, Analyst and Administrator are backend-owned demo identities.
- Document access is enforced with metadata filters, not namespace membership alone.
- The intended hierarchy is Viewer: public/internal; Analyst: additionally confidential;
  Administrator: additionally restricted. The definitions in app/auth/models.py are authoritative.
- Tool permissions are checked independently by the server-side registry.
- A model-provided role or tool argument cannot grant access.
- Known demo credentials are allowed only when API_TOKENS is absent.
- An explicit valid API_TOKENS mapping replaces demo credentials. `{}` disables all
  API-key access. An explicit empty string, malformed JSON, invalid values or unknown
  users fail startup validation; runtime authentication also fails closed.
- Do not expose the Streamlit identity selector as production authentication.

## Retrieval

- Pinecone namespaces represent document_type.
- Hybrid search combines dense embeddings and sparse BM25 in the intended compatible
  dot-product index, weighted by HYBRID_ALPHA.
- Heading-aware chunks include descriptive context for attribution.
- Query embeddings must match indexed document embeddings in model, dimensions and formatting.
- The saved BM25 parameters must match the sparse vectors already indexed.
- Missing BM25 parameters permit dense-only degraded operation, not verified hybrid search.
- Score thresholds, diversity caps and dominant-document expansion are heuristics.
  They are not a learned reranker or calibrated confidence estimator.

## Provider configuration and rationale

- Chat and embedding clients currently share BASE_URL and API_KEY. Independently
  configured chat/embedding endpoint routing is not claimed.
- The example environment describes one compatible hosted endpoint with explicit
  model placeholders. A local gateway is an alternative if it serves both required APIs.
- Actual tested provider/model IDs and embedding dimensions must be recorded from
  the working environment; they cannot be inferred from historical Qwen/vLLM examples.
- Local inference offers deployment control but requires serving resources and operations.
  Hosted inference reduces serving work but adds network dependency, usage charges and
  provider data-handling considerations.
- Local inference does not mean all data stays on the machine: Pinecone and LangSmith
  are external dependencies. Traces can contain prompts, evidence and outputs.
- Model/agent calls are distinct from deterministic output validation. The response
  validator is code, not a separate model call. Current production wiring constructs
  non-thinking chat wrappers; do not claim thinking-mode behavior without verifying it.

## Research and analysis

- Research uses a bounded Python-plan representation, targeted sections, batching,
  recursive splitting and aggregation. It does not execute arbitrary generated Python.
- Relevant findings require supporting rendered chunks belonging to the same document.
- Coverage can be incomplete because of selection limits, retrieval misses, truncated
  context, model failures or aggregation loss. Degradation must be disclosed.
- Python analysis computes structured facts/comparisons; it is not an arbitrary-code sandbox.
- Date-relative requests must state a reference date. Existing assessment examples use
  October 2026; verify explicit date filters rather than relying on the phrase "last year".

## Memory, concurrency and streaming

- Memory persists across turns within one process-local session, not across durable restarts.
- Session ownership prevents cross-user reuse. Same-session requests are serialized.
- One API worker is used because session, memory and rate-limit state are process-local.
- Whole-turn timeout includes session-lock waiting and graph execution.
- Provisional tokens are not approved answers. Keep preview disabled for safer demos.
- The final response payload is authoritative. The UI distinguishes blocked, degraded
  and ordinary completion and uses final validation data when supplied.

## Security and observability

- Public node errors use stable codes instead of exception messages.
- Internal logs may still contain tracebacks. Safe client errors do not establish
  complete log/trace redaction; access, retention and redaction controls remain necessary.
- Citation-ID validity is not proof that every claim is entailed by its source.
- final_ok describes the selected output policy result, not universal factual correctness.
- Actual conversation, node, retrieval and tool traces must be verified in LangSmith.

## Deferred capabilities

- The reviewed enterprise adapter is a local mock, not MCP transport. MCP server/client
  integration, agent enterprise routing and complete tool-event plumbing remain separate
  tasks until implemented and demonstrated.
- Long-term memory, learned reranking, human approvals and feedback loops are not claimed.
- Production SSO, distributed state, TLS deployment and a full security audit are deferred.

## Assessment deliverables

- The brief specifies a 45-minute public demo video. Do not reinterpret this as five
  minutes without explicit evaluator approval.
- The public repository, architecture diagram, video link, LangSmith walkthrough and
  explanation of assumptions/trade-offs must be checked before submission.
- Passing automated tests does not by itself verify live provider access, retrieval
  quality, trace delivery, container readiness or public submission access.

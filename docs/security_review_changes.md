# Security and reliability update notes

## Scope

Manual-merge update against commit 57c173dcf435b9becd8d036df3ca07e0c282765e.
No remote commit, push, deployment, index recreation or corpus regeneration is required.
This update addresses selected static-review findings, not complete assessment compliance.

## Implemented changes

- Replace raw exception details in graph failure activity with stable public errors.
- Sanitize research provider and batch-failure messages.
- Do not authorize citations using identifiers from the user's question.
- Revalidate output after citation/placeholder sanitization and fail closed on remaining blocking issues.
- Preserve original validation status and add `final_ok` for the selected final text.
- Mark failed retrieval, failed research and replaced outputs degraded.
- Require rendered, same-document chunk evidence for relevant research findings.
- Propagate retrieval degradation into research warnings.
- Fail fast on errors classified permanent by the existing provider-error classifier.
- Distinguish all-batch analysis failure from no relevant documents.
- Add redacted registry tool spans and a shared authorized-search span.
- Populate Docker build exclusions and declare the directly imported tqdm dependency.

## Model configuration

The inspected embedding client uses Settings.base_url and Settings.api_key.
A separate embedding endpoint setting is not implemented by this update.
The configured endpoint must support the selected embedding API/model.
Do not switch embedding model/dimensions without checking the indexed document vectors.
API port is 8000 and UI port is 3000. Use http://api:8000 inside Compose.

## RAG stage impact

- chunk/embed/store: no indexing or model changes; tqdm dependency is explicit.
- retrieve: redacted tracing spans cover authorized ordinary and research search.
- rerank: no learned reranker added.
- generate/validate: evidence-based citation authorization and fail-closed final output.
- research aggregation: evidence ownership and completeness warnings are enforced.

## Validation

The previously reported 14 passing drills predate this update. They do not validate these changes.
Run the full regression suite and new tests after merging:

    python -m pytest -q
    python -m scripts.run_failure_drills
    docker compose config --quiet
    docker compose build api ui

Inspect real UI events and LangSmith traces. Tool trace input/output payloads are redacted;
exception tracing and unrelated graph/model traces still need a full privacy review.
A post-sanitization validation pass does not establish semantic entailment of every sentence.

## Outstanding work

- MCP server/client integration and agent routing to service_catalog are not included.
- Live UI tool activity callbacks remain to be wired consistently.
- Provider errors in health endpoints and all other event sources still need inspection.
- Real LangSmith parentage, provider startup and complete redaction require runtime verification.
- No dependency lockfile, distributed state, learned reranker or arbitrary-code sandbox is added.
- Video, public accessibility and demo evidence must be verified separately.

The assessment permits hardcoded identities and session-scoped memory.
MCP is lower priority but remains a stated requirement; do not label a mock adapter MCP.
Long-term memory, learned reranking and approval workflows are bonuses.

## Trace failure isolation

New tool/search tracing uses an async wrapper that falls back only before execution,
or returns the already completed result if trace finalization fails. It does not
repeat a started incomplete handler. Tool arguments, identity and outputs are
redacted in these spans. Span names are generic; per-tool naming is future work.

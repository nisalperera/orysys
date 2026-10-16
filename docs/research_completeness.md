# Research completeness and aggregation fallbacks

## Empty and inconclusive analysis outcomes

No selected documents means no accessible matches. All failed batches mean analysis
failed. Selected documents with rejected/missing findings mean supported relevance
could not be established, not that the documents were irrelevant. Only complete,
warning-free explicit classification permits a scoped no-relevant-documents outcome.

Automatic summaries label incomplete downtime as a known downtime subtotal.
This is conservative at global metric coverage level; per-cause measurement coverage
is not introduced by this small update.

The final-delivery tests use the real LangGraph builder, ChatService and FastAPI
with injected offline research fixtures. Run them locally; they were not executed
in the package-generation environment.

## Measurement coverage

Analysis keeps backwards-compatible totals as known sums and adds metric_coverage.
For duration_minutes and failed_transactions it reports applicable, total_documents,
known_documents, missing_doc_ids, complete, and known_subtotal.

Measured zero is valid. Missing, negative, boolean, string or fractional metadata
is not a measured value. For the incident-count contract these metrics are
non-negative integer measurements.

The executor supplies document_type. Known non-incident documents are excluded
from incident measurement coverage. Direct legacy analysis callers that omit
this field are assumed to supply incident rows; supply document_type explicitly
when analyzing mixed collections.

Coverage concerns relevant analyzed documents, not every document in the organization.
Selection limits, missing evidence and failed batches are separate limitations.
Complete measurement coverage does not imply complete document retrieval.

Incomplete measurements mark research degraded and prohibit claiming complete
collection-wide metric totals/rankings in the reduction instructions. Final text
also receives a deterministic limitation note, rather than relying only on model
compliance. Existing numeric totals remain known subtotals; no data is invented.

## Partial reduction

If a partial summarizer fails, fallback retains complete finding records within
1500 characters. Oversized records are omitted, not sliced. It reports retained
and omitted counts through partial_reduce_fallback activity and degraded reasons.
A fallback with no lost records is still disclosed as a model-stage failure.

## Final disclosure

The reducer receives bounded, sanitized completeness notes. Final results append
those notes deterministically, including on automatic-summary fallback. Duplicate
identical limitation footers are avoided. Arbitrary exception details are not
copied into the public limitation text.

The existing degraded result flag remains authoritative for the UI. Added notes
do not guarantee every model claim is entailed or consistent; broader answer
quality evaluation remains necessary.

## Stage and configuration impact

Research aggregation and generation are affected. There are no changes to
chunking, embedding, storage, retrieval ranking, model endpoints or index contents.
No new environment variables or dependencies are introduced.

## Tests

Run:

    python -m pytest -q tests/test_measurement_coverage.py tests/test_research_completeness.py
    python -m pytest -q
    python -m scripts.run_failure_drills

Fifteen helper cases passed in an isolated package. Executor tests use the existing
injected FakeLLM/FakeRetriever fixtures and need to be run in the complete repository.
No live provider, Docker or LangSmith validation is claimed by this package.

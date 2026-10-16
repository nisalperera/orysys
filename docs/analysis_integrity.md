# Research analysis integrity

RAG/research stage affected: aggregation before generation. No chunking, embedding,
index, retrieval ranking, model routing or corpus changes are introduced.

## Unit of counting

- total_documents counts unique document IDs.
- total_findings counts supplied finding records.
- Incident rows, numeric totals, month/service/severity counts use one row per document.
- Root-cause recurrence counts distinct documents per canonical label.
- Repeated findings for the same document cannot create false recurrence.
- Supporting chunk IDs are merged without duplicates in each incident row.

## Multiple cause labels

Distinct canonical cause labels for one document are preserved rather than choosing
one silently. root_cause_conflicts records these cases and root_cause_groups_overlap
is true. Each cause group counts that document once, while global incident totals
count it only once. Therefore cause-group totals are overlapping attribution and
must not be summed to reconstruct global totals.

The executor marks this ambiguity as degraded so the final result can disclose it.
Existing token-overlap clustering remains a heuristic, not causal verification.
Evidence arrays are provenance carried from findings, not newly checked retrieval
proof; the existing research evidence policy must still run upstream.

## Numeric extraction

Supported count values are non-negative integers written as plain digits or standard
comma-separated thousands groups, for example 8670, 8,670 and 1,234,567.
Malformed groups, decimals, negatives and space-separated values are left unparsed.
Transaction counts are expected to occupy their field value line; explanatory text
on the same line is not accepted by this strict extractor.
Duration accepts the same integer forms followed by the word minutes.

Missing/invalid numeric metadata contributes zero to the aggregate sum, meaning
known measured total, not proof missing values were actually zero. Individual rows
retain missing fields; downstream summaries should disclose incomplete measurements.

## Validation

New focused tests cover duplicate counting, evidence preservation, recurrence,
cause-label ambiguity, integer formats, missing metadata and empty inputs.
Twenty focused tests passed in an isolated package containing the actual replacement
module. The complete application suite and live research workflow were not run here.

    python -m pytest -q tests/test_analysis_integrity.py
    python -m pytest -q
    python -m scripts.run_failure_drills

Provider examples and local-server limitations are documented in vllm_serving.md.

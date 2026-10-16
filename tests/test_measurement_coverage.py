import pytest
from app.rlm.completeness import (
    measurement_coverage, coverage_reasons, bounded_records,
    safe_completeness_notes, append_completeness_notes,
)


def test_missing_values_are_distinct_from_measured_zero():
    coverage = measurement_coverage(
        [{"doc_id": "A"}, {"doc_id": "B"}],
        {"A": {"document_type": "incident", "failed_transactions": 0},
         "B": {"document_type": "incident"}},
    )["failed_transactions"]
    assert coverage["known_documents"] == 1
    assert coverage["missing_doc_ids"] == ["B"]
    assert coverage["known_subtotal"] == 0 and coverage["complete"] is False


def test_all_measured_zero_is_complete():
    coverage = measurement_coverage([{"doc_id": "A"}], {"A": {"failed_transactions": 0}})
    assert coverage["failed_transactions"]["complete"] is True


@pytest.mark.parametrize("invalid", [None, -1, True, "100", 1.5])
def test_invalid_numeric_metadata_is_missing_not_measured(invalid):
    item = measurement_coverage([{"doc_id": "A"}], {"A": {"failed_transactions": invalid}})["failed_transactions"]
    assert item["known_documents"] == 0 and item["missing_doc_ids"] == ["A"]


def test_nonincident_documents_do_not_create_missing_incident_metrics():
    coverage = measurement_coverage([{"doc_id": "RB-001"}], {"RB-001": {"document_type": "runbook"}})
    assert all(not metric["applicable"] for metric in coverage.values())
    assert coverage_reasons({"metric_coverage": coverage}) == []


def test_duplicate_rows_do_not_inflate_metric_coverage():
    coverage = measurement_coverage([{"doc_id": "A"}, {"doc_id": "A"}], {"A": {"duration_minutes": 3}})
    assert coverage["duration_minutes"]["total_documents"] == 1
    assert coverage["duration_minutes"]["known_subtotal"] == 3


def test_bounded_fallback_preserves_whole_records_and_citations():
    first = "[INC-2026-007] " + "x" * 900
    second = "[INC-2026-011] " + "y" * 900
    result = bounded_records([first, second], 1500)
    assert result == {"text": first, "retained": 1, "omitted": 1}


def test_bounded_fallback_keeps_all_small_records():
    result = bounded_records(["[A] one", "[B] two"])
    assert result["text"] == "[A] one\n[B] two" and result["omitted"] == 0


def test_oversized_records_are_omitted_not_sliced():
    result = bounded_records(["x" * 2000])
    assert result == {"text": "", "retained": 0, "omitted": 1}


def test_completeness_notes_do_not_echo_arbitrary_error_details():
    notes = safe_completeness_notes({}, ["private-endpoint-marker"])
    assert notes and "private-endpoint-marker" not in " ".join(notes)


def test_final_notes_are_idempotent():
    answer = append_completeness_notes("Answer", {}, ["selection truncated to 40 documents"])
    assert append_completeness_notes(answer, {}, ["selection truncated to 40 documents"]) == answer


def test_partial_fallback_retention_counts_are_disclosed():
    notes = safe_completeness_notes({}, ["Partial aggregation failed; retained 1 of 3 complete records"])
    assert "retained 1 of 3" in " ".join(notes)
    assert "omitted" in " ".join(notes)

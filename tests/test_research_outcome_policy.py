import pytest
from app.rlm.completeness import no_findings_outcome, downtime_label


def test_empty_selection_is_not_an_analysis_failure():
    text, incomplete = no_findings_outcome([], [], [])
    assert "No accessible documents" in text and incomplete is False


def test_all_batch_failures_are_not_reported_as_irrelevance():
    text, incomplete = no_findings_outcome(["A"], [], ["failed"])
    assert "could not be analysed" in text and incomplete
    assert "No relevant documents" not in text


def test_rejected_findings_are_inconclusive():
    text, incomplete = no_findings_outcome(["A"], [], [None], True)
    assert "could not establish supported relevance" in text and incomplete
    assert "No relevant documents" not in text


def test_complete_explicit_irrelevance_is_scoped():
    text, incomplete = no_findings_outcome(["A"], ["A"], [None], False)
    assert text == "No relevant documents were identified within the analysed scope."
    assert incomplete is False


def test_partly_classified_selection_is_inconclusive():
    text, incomplete = no_findings_outcome(["A", "B"], ["A"], [None], False)
    assert incomplete and "supported relevance" in text


def test_warnings_prevent_claiming_complete_irrelevance():
    _, incomplete = no_findings_outcome(["A"], ["A"], [None], True)
    assert incomplete


def test_mixed_failed_and_nonfailed_batches_are_inconclusive():
    text, incomplete = no_findings_outcome(["A", "B"], ["A"], [None, "failed"], False)
    assert incomplete and "supported relevance" in text


def test_incomplete_downtime_is_labelled_as_known_subtotal():
    assert downtime_label({"metric_coverage": {"duration_minutes": {
        "applicable": True, "complete": False,
    }}}) == "min known downtime subtotal"


def test_complete_downtime_preserves_existing_label():
    assert downtime_label({"metric_coverage": {"duration_minutes": {
        "applicable": True, "complete": True,
    }}}) == "min downtime"


def test_legacy_analysis_preserves_existing_label():
    assert downtime_label({}) == "min downtime"

import pytest
from app.tools.python_analysis import analyze_findings, extract_facts


@pytest.mark.parametrize("text,expected", [
    ("8670", 8670), ("8,670", 8670), ("1,234,567", 1234567), ("0", 0),
])
def test_transaction_integer_formats(text, expected):
    assert extract_facts(f"**Failed transactions (approx):** {text}\n")["failed_transactions"] == expected


@pytest.mark.parametrize("text", ["8,67", "8,,670", "8,670,", "8 670", "8670.5", "-12", "unknown", ""])
def test_invalid_transaction_formats_are_not_partially_parsed(text):
    assert "failed_transactions" not in extract_facts(f"**Failed transactions (approx):** {text}\n")


def test_missing_transaction_field_is_not_invented():
    assert "failed_transactions" not in extract_facts("**Severity:** P1\n")


def test_duration_format_and_other_fields_remain_supported():
    facts = extract_facts("**Duration:** 1,234 minutes\n**Severity:** P1\n**Affected service:** payments-api\n")
    assert facts == {"duration_minutes": 1234, "severity": "P1", "service": "payments-api"}


def finding(doc_id, cause="Gateway timeout", evidence=None):
    return {"doc_id": doc_id, "root_cause": cause, "service": "payments-api", "evidence": evidence or []}


def metadata():
    return {"A": {"created_date": "2026-01-01", "severity": "P1", "service": "payments-api",
                  "duration_minutes": 71, "failed_transactions": 7840}}


def test_duplicate_findings_do_not_duplicate_documents_or_totals():
    result = analyze_findings([finding("A"), finding("A")], metadata())
    assert result["total_documents"] == 1 and result["total_findings"] == 2
    assert len(result["incidents"]) == 1
    assert result["totals"] == {"downtime_minutes": 71, "failed_transactions": 7840}
    assert result["by_month"] == {"2026-01": 1}
    assert result["by_severity"] == {"P1": 1}
    assert result["by_root_cause"][0]["count"] == 1
    assert result["by_root_cause"][0]["doc_ids"] == ["A"]
    assert result["recurring"] == []


def test_duplicate_findings_preserve_unique_evidence():
    result = analyze_findings([
        finding("A", evidence=["A#0"]), finding("A", evidence=["A#1", "A#0"]),
    ], metadata())
    assert result["incidents"][0]["evidence"] == ["A#0", "A#1"]


def test_distinct_documents_still_count_as_recurrence():
    meta = metadata()
    meta["B"] = dict(meta["A"], created_date="2026-02-01")
    result = analyze_findings([finding("A"), finding("A"), finding("B")], meta)
    assert result["total_documents"] == 2
    assert result["by_root_cause"][0]["count"] == 2
    assert result["recurring"] == ["Gateway timeout"]
    assert result["totals"]["failed_transactions"] == 15680


def test_distinct_cause_labels_are_preserved_without_double_counting_global_totals():
    result = analyze_findings([
        finding("A", "Gateway timeout"), finding("A", "Database deadlock"),
    ], metadata())
    assert result["totals"]["downtime_minutes"] == 71
    assert result["root_cause_groups_overlap"] is True
    assert set(result["root_cause_conflicts"]["A"]) == {"Gateway timeout", "Database deadlock"}
    assert len(result["by_root_cause"]) == 2
    assert all(item["count"] == 1 for item in result["by_root_cause"])
    assert result["recurring"] == []


def test_missing_numeric_metadata_is_safe():
    result = analyze_findings([finding("A")], {"A": {"duration_minutes": None, "failed_transactions": None}})
    assert result["totals"] == {"downtime_minutes": 0, "failed_transactions": 0}
    assert result["longest_downtime"] is None


def test_empty_findings_are_safe():
    result = analyze_findings([], {})
    assert result["total_documents"] == 0
    assert result["incidents"] == [] and result["recurring"] == []

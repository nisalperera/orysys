from app.rlm.guard import reconcile_select
from app.tools.python_analysis import analyze_findings, extract_facts


def test_department_dropped_when_not_named():
    args, notes = reconcile_select(
        {"department": "payments", "keywords": ["payment"]},
        "Summarize payment failures last year",
        {"payments", "cards"},
    )

    assert args["department"] is None
    assert args["keywords"] == ["payment"]
    assert len(notes) == 1


def test_department_kept_when_named_case_insensitive():
    source = {"department": "cards", "date_from": "2025-10-16"}

    args, notes = reconcile_select(
        source,
        "Show incidents in the Cards department",
        {"cards"},
    )

    assert args == source
    assert notes == []
    assert args is not source


def test_no_department_no_change_and_input_not_mutated():
    source = {"department": None}

    assert reconcile_select(
        source, "anything", set()
    ) == ({"department": None}, [])

    source_with_department = {"department": "payments"}

    reconcile_select(source_with_department, "x", set())

    assert source_with_department["department"] == "payments"


def _meta(date, severity, minutes, transactions, service="svc"):
    return {
        "created_date": date,
        "severity": severity,
        "duration_minutes": minutes,
        "failed_transactions": transactions,
        "service": service,
    }


def test_analysis_has_incident_table_and_extremes():
    metadata = {
        "A": _meta("2026-01-21", "P2", 38, 3690),
        "B": _meta("2026-07-15", "P1", 71, 7840),
        "C": _meta("2026-09-03", "P2", 44, 8670),
    }
    findings = [
        {
            "doc_id": doc_id,
            "root_cause": "Third-party gateway timeouts",
            "service": "",
        }
        for doc_id in metadata
    ]

    analysis = analyze_findings(findings, metadata)

    assert [
        incident["doc_id"] for incident in analysis["incidents"]
    ] == ["A", "B", "C"]
    assert analysis["longest_downtime"]["doc_id"] == "B"
    assert analysis["most_failed_transactions"]["doc_id"] == "C"
    assert analysis["by_severity"] == {"P1": 1, "P2": 2}
    assert analysis["totals"] == {
        "downtime_minutes": 153,
        "failed_transactions": 20200,
    }


def test_analysis_handles_missing_facts():
    analysis = analyze_findings(
        [{"doc_id": "X", "root_cause": ""}],
        {},
    )

    assert analysis["longest_downtime"] is None
    assert analysis["incidents"][0]["severity"] is None


def test_extract_facts_unchanged():
    text = (
        "**Severity:** P1  \n"
        "**Duration:** 62 minutes\n"
        "**Failed transactions (approx):** 2030\n"
        "**Affected service:** payments-api"
    )

    assert extract_facts(text)["failed_transactions"] == 2030

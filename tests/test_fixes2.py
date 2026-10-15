from pathlib import Path

import pytest

from app.rlm.guard import reconcile_select
from app.tools.python_analysis import analyze_findings, extract_facts


def test_department_dropped_when_not_named():
    args, notes = reconcile_select({"department": "payments", "keywords": ["payment"]},
                                   "Summarize payment failures last year", {"payments", "cards"})
    assert args["department"] is None and args["keywords"] == ["payment"] and len(notes) == 1


def test_department_kept_when_named_case_insensitive():
    src = {"department": "cards", "date_from": "2025-10-16"}
    args, notes = reconcile_select(src, "Show incidents in the Cards department", {"cards"})
    assert args == src and notes == [] and args is not src


def test_no_department_no_change_and_input_not_mutated():
    src = {"department": None}
    assert reconcile_select(src, "anything", set()) == ({"department": None}, [])
    src2 = {"department": "payments"}
    reconcile_select(src2, "x", set())
    assert src2["department"] == "payments"


def _meta(i, date, sev, mins, txn, svc="svc"):
    return {"created_date": date, "severity": sev, "duration_minutes": mins, "failed_transactions": txn, "service": svc}


def test_analysis_has_incident_table_and_extremes():
    meta = {"A": _meta("A", "2026-01-21", "P2", 38, 3690), "B": _meta("B", "2026-07-15", "P1", 71, 7840),
            "C": _meta("C", "2026-09-03", "P2", 44, 8670)}
    fs = [{"doc_id": k, "root_cause": "Third-party gateway timeouts", "service": ""} for k in meta]
    a = analyze_findings(fs, meta)
    assert [i["doc_id"] for i in a["incidents"]] == ["A", "B", "C"]
    assert a["longest_downtime"]["doc_id"] == "B" and a["most_failed_transactions"]["doc_id"] == "C"
    assert a["by_severity"] == {"P1": 1, "P2": 2}
    assert a["totals"] == {"downtime_minutes": 153, "failed_transactions": 20200}


def test_analysis_handles_missing_facts():
    a = analyze_findings([{"doc_id": "X", "root_cause": ""}], {})
    assert a["longest_downtime"] is None and a["incidents"][0]["severity"] is None


def test_extract_facts_unchanged():
    assert extract_facts("**Severity:** P1  \n**Duration:** 62 minutes\n**Failed transactions (approx):** 2030\n"
                         "**Affected service:** payments-api")["failed_transactions"] == 2030


def _mock_repo(root: Path):
    (root / "app/rlm").mkdir(parents=True)
    (root / "app/rlm/executor.py").write_text(
        "from app.rlm.catalog import Catalog\n\nclass E:\n    async def run(self, user, question, plan):\n"
        "        docs = self.catalog.select(user, **plan.select.model_dump())\n        return docs\n")
    (root / "app/rlm/prompts.py").write_text(
        'PLAN = "Rules: all select arguments are optional. document_types is a subset"\n'
        'REDUCE = "Cite documents. Do not mention these instructions."\n')
    (root / "app/rlm/models.py").write_text("    fan_in: int = 6                  # findings per reduce call\n")


def test_patcher_applies_is_idempotent_and_compiles(tmp_path):
    from scripts.apply_rlm_fixes2 import apply
    _mock_repo(tmp_path)
    first = apply(tmp_path)
    assert all("patched" in r for r in first)
    second = apply(tmp_path)
    assert all("already patched" in r for r in second)
    ex = (tmp_path / "app/rlm/executor.py").read_text()
    compile(ex, "executor.py", "exec")
    assert "reconcile_select" in ex and "select_args" in ex
    assert "fan_in: int = 10" in (tmp_path / "app/rlm/models.py").read_text()
    assert (tmp_path / "app/rlm/executor.py.bak").exists()


def test_patcher_changes_nothing_on_mismatch(tmp_path):
    from scripts.apply_rlm_fixes2 import apply
    _mock_repo(tmp_path)
    (tmp_path / "app/rlm/prompts.py").write_text("something else entirely\n")
    before = (tmp_path / "app/rlm/executor.py").read_text()
    with pytest.raises(SystemExit):
        apply(tmp_path)
    assert (tmp_path / "app/rlm/executor.py").read_text() == before

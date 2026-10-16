from types import SimpleNamespace
from app.rlm.evidence_policy import supported_findings
from app.rlm.models import DocFinding


def finding(doc_id, evidence):
    return DocFinding.model_validate({
        "doc_id": doc_id, "relevant": True, "summary": "Supported incident finding",
        "root_cause": "Timeout", "service": "payments-api", "evidence": evidence,
    })


def test_foreign_document_chunk_does_not_support_finding():
    hit = SimpleNamespace(chunk_id="INC-2026-007#0", doc_id="INC-2026-007")
    result, warnings = supported_findings(
        [finding("INC-2026-011", [hit.chunk_id])], {hit.chunk_id}, [hit]
    )
    assert result == [] and warnings


def test_valid_same_document_evidence_is_retained():
    hit = SimpleNamespace(chunk_id="INC-2026-007#0", doc_id="INC-2026-007")
    result, warnings = supported_findings(
        [finding(hit.doc_id, [hit.chunk_id])], {hit.chunk_id}, [hit]
    )
    assert len(result) == 1 and result[0].evidence == [hit.chunk_id] and not warnings


def test_unrendered_evidence_is_not_accepted():
    hit = SimpleNamespace(chunk_id="INC-2026-007#0", doc_id="INC-2026-007")
    result, warnings = supported_findings([finding(hit.doc_id, [hit.chunk_id])], set(), [hit])
    assert result == [] and warnings

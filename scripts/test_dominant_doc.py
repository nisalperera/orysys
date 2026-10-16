from app.retrieval.hybrid import apply_post_filters, doc_limits
from app.retrieval.schemas import Hit


def h(doc, n, score):
    return Hit(chunk_id=f"{doc}#{n}", doc_id=doc, title="t", section="s", document_type="runbook", department="d",
               access_level="internal", created_date="2026-01-01", score=score, text="x")


ALLOWED = {"internal"}


def test_dominant_document_keeps_all_its_sections():
    hits = [h("RB-001", 0, 0.703), h("RB-001", 2, 0.665), h("RB-001", 1, 0.60), h("RB-004", 2, 0.35), h("RB-003", 1, 0.335)]
    final, _, _, capped = apply_post_filters(hits, ALLOWED, 0.30, 2, 8)
    assert [x.chunk_id for x in final].count("RB-001#1") == 1 and capped == 0 and len(final) == 5


def test_similar_scores_keep_the_diversity_cap():
    hits = [h("A", 0, 0.70), h("A", 1, 0.69), h("A", 2, 0.68), h("B", 0, 0.65)]
    final, _, _, capped = apply_post_filters(hits, ALLOWED, 0.30, 2, 8)
    assert [x.chunk_id for x in final] == ["A#0", "A#1", "B#0"] and capped == 1


def test_single_document_or_cap_disabled_is_unchanged():
    assert doc_limits([h("A", 0, 0.9), h("A", 1, 0.8)], 2) == {}
    assert doc_limits([h("A", 0, 0.9), h("B", 0, 0.1)], 0) == {}
    assert doc_limits([], 2) == {}


def test_dominance_threshold_is_strict_enough():
    assert doc_limits([h("A", 0, 0.9), h("B", 0, 0.6)], 2) == {}
    assert doc_limits([h("A", 0, 0.9), h("B", 0, 0.5)], 2) == {"A": 6}

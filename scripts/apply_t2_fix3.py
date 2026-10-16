"""T2 fix 3: small-to-big expansion for the document a question is clearly about.

Observed: "runbook for connection pool saturation" retrieved RB-001 Detection (0.70) and Escalation (0.67) but the
Mitigation section was dropped by the 2 chunks per document cap, so the answer left out the steps that matter.
Rule: if the best document scores at least 1.6x the best chunk of every other document, the question is about that
document and it may contribute up to 6 chunks. With similar scores the cap of 2 still keeps results diverse.

Also adds dropped_by_cap and dropped_below_min to the retrieval event.
Run once from the repo root (.bak backups, anchors checked before writing).
"""
from pathlib import Path

HELPER = '''DOMINANT_RATIO = 1.6
DOMINANT_LIMIT = 6


def doc_limits(relevant: list, max_per_doc: int) -> dict[str, int]:
    """Small-to-big: let a clearly dominant document contribute more chunks (needs at least two documents)."""
    if not max_per_doc:
        return {}
    best: dict[str, float] = {}
    for h in relevant:
        best[h.doc_id] = max(best.get(h.doc_id, 0.0), h.score)
    ranked = sorted(best.items(), key=lambda kv: -kv[1])
    if len(ranked) >= 2 and ranked[0][1] >= DOMINANT_RATIO * ranked[1][1]:
        return {ranked[0][0]: max(max_per_doc, DOMINANT_LIMIT)}
    return {}


'''

EDITS = {
    "app/retrieval/hybrid.py": [
        ("def apply_post_filters(hits: list[Hit], allowed_levels: set[str], min_score: float, max_per_doc: int,\n",
         HELPER + "def apply_post_filters(hits: list[Hit], allowed_levels: set[str], min_score: float, max_per_doc: int,\n"),
        ("    per_doc: Counter = Counter()\n    capped: list[Hit] = []\n    for h in relevant:\n"
         "        if max_per_doc and per_doc[h.doc_id] >= max_per_doc:\n",
         "    per_doc: Counter = Counter()\n    capped: list[Hit] = []\n    limits = doc_limits(relevant, max_per_doc)\n    for h in relevant:\n"
         "        if max_per_doc and per_doc[h.doc_id] >= limits.get(h.doc_id, max_per_doc):\n"),
    ],
    "app/graph/nodes.py": [
        ('"no_relevant_results": res.no_relevant_results, "alpha": res.alpha,',
         '"no_relevant_results": res.no_relevant_results, "dropped_by_cap": res.dropped_by_doc_cap,\n'
         '            "dropped_below_min": res.dropped_below_min_score, "alpha": res.alpha,'),
    ],
}


def apply(root: Path = Path(".")) -> list[str]:
    report, out = [], {}
    for rel, edits in EDITS.items():
        text = (root / rel).read_text()
        for old, new in edits:
            if new in text:
                report.append(f"{rel}: already patched")
            elif old in text:
                text = text.replace(old, new, 1)
                report.append(f"{rel}: patched")
            else:
                raise SystemExit(f"{rel}: expected text not found, apply manually:\n{old}")
        out[rel] = text
    for rel, text in out.items():
        p = root / rel
        if p.read_text() != text:
            p.with_suffix(p.suffix + ".bak").write_text(p.read_text())
            p.write_text(text)
    return report


if __name__ == "__main__":
    print("\n".join(apply()))

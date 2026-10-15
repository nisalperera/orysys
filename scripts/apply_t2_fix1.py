"""T2 fix 1 (run once from the repo root, makes .bak backups, all anchors are checked before writing).

1. tests/graph_helpers.py: FakeSearch built a RetrievalResult without the required `alpha` and `applied_filter`
   fields, so every graph test that reached retrieval saw a validation error and the (correct) "unable to search"
   fallback. That was a test helper bug, not a production bug.
2. app/graph/nodes.py: log retrieval, research and response failures. They were reported only as activity events,
   which made this failure invisible in the console.
"""
import sys
from pathlib import Path

EDITS = {
    "tests/graph_helpers.py": [(
        'return RetrievalResult(hits=self.hits, namespaces_searched=["incident"], no_relevant_results=self.no_relevant and not self.hits)',
        'return RetrievalResult(hits=self.hits, namespaces_searched=["incident"], alpha=0.6, applied_filter={},\n'
        '                               no_relevant_results=self.no_relevant and not self.hits)')],
    "app/graph/nodes.py": [
        ('        meta = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"[:300]}\n',
         '        meta = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"[:300]}\n'
         '        log.warning("retrieval failed: %s", meta["error"])\n'),
        ('        err = f"{type(exc).__name__}: {exc}"[:300]\n',
         '        err = f"{type(exc).__name__}: {exc}"[:300]\n        log.warning("research failed: %s", err)\n'),
        ('        deps.emit(rid, "generation_failed", "response", error=f"{type(exc).__name__}: {exc}"[:300])\n',
         '        log.warning("response generation failed: %s: %s", type(exc).__name__, exc)\n'
         '        deps.emit(rid, "generation_failed", "response", error=f"{type(exc).__name__}: {exc}"[:300])\n'),
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

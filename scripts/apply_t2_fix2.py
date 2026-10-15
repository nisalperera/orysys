"""T2 fix 2 (run once from the repo root, .bak backups, anchors checked before writing).

1. retrieval event now lists the retrieved chunks (id, score, section), so the activity panel shows WHAT evidence the answer used
2. retrieval returns 8 chunks instead of 6 (the runbook answer missed the mitigation steps, see docs)
3. chat_cli: newline after streamed tokens, longer event lines
"""
from pathlib import Path

CHUNKS = ('            "chunks": [{"id": h["chunk_id"], "score": round(h["score"], 3), "section": h["section"]} for h in hits],\n')
EDITS = {
    "app/graph/nodes.py": [
        ('    meta = {"status": "ok", "hits": len(hits), "namespaces": res.namespaces_searched,\n',
         '    meta = {"status": "ok", "hits": len(hits), "namespaces": res.namespaces_searched,\n' + CHUNKS),
        ("req = SearchRequest(query=q, top_k=6, **filters)", "req = SearchRequest(query=q, top_k=8, **filters)"),
        ('req = SearchRequest(query=state["question"][:1000], top_k=6)', 'req = SearchRequest(query=state["question"][:1000], top_k=8)'),
    ],
    "scripts/chat_cli.py": [
        ("def render(ev: dict) -> None:\n", "_streaming = False\n\n\ndef render(ev: dict) -> None:\n"),
        ('    t, node, d = ev["type"], ev.get("node"), ev["data"]\n    if t == "token":\n        print(d["text"], end="", flush=True)\n',
         '    global _streaming\n    t, node, d = ev["type"], ev.get("node"), ev["data"]\n'
         '    if t != "token" and _streaming:\n        print()\n        _streaming = False\n'
         '    if t == "token":\n        _streaming = True\n        print(d["text"], end="", flush=True)\n'),
        ("[:260]", "[:420]"),
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

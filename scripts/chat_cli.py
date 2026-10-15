"""Terminal client for the SSE API: prints the activity panel events and streams the answer.

python -m scripts.chat_cli analyst1 "What is the runbook for connection pool saturation?"
python -m scripts.chat_cli viewer1 "And how was it fixed?" --session my-session-0001 --url http://localhost:8080
"""
import argparse
import json
import sys
import uuid

import httpx

KEYS = {"viewer1": "dev-viewer-key", "analyst1": "dev-analyst-key", "admin1": "dev-admin-key"}


def iter_sse(lines):
    """Parses SSE lines into event dicts (the server puts the full event JSON in `data`)."""
    data = []
    for line in lines:
        if line.startswith(":"):
            continue
        if line == "":
            if data:
                yield json.loads("\n".join(data))
                data = []
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())
    if data:
        yield json.loads("\n".join(data))


_streaming = False


def render(ev: dict) -> None:
    global _streaming
    t, node, d = ev["type"], ev.get("node"), ev["data"]
    if t != "token" and _streaming:
        print()
        _streaming = False
    if t == "token":
        _streaming = True
        print(d["text"], end="", flush=True)
    elif t == "final":
        print(f"\n\n=== FINAL ({d.get('latency_ms')} ms, intent={d.get('intent')}, degraded={d.get('degraded')}) ===")
        print(d["answer"])
        print("citations:", [c["doc_id"] for c in d.get("citations", [])], "| validation:", d.get("validation", {}).get("action"))
    elif t in ("node_end", "node_start"):
        return
    else:
        print(f"\n[{t}{'/' + node if node else ''}] {json.dumps(d, default=str)[:420]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("user", choices=KEYS)
    ap.add_argument("message")
    ap.add_argument("--session", default=uuid.uuid4().hex)
    ap.add_argument("--url", default="http://localhost:8080")
    a = ap.parse_args()
    print(f"session: {a.session}")
    with httpx.stream("POST", f"{a.url}/chat/stream", headers={"X-API-Key": KEYS[a.user]},
                      json={"message": a.message, "session_id": a.session}, timeout=None) as r:
        if r.status_code != 200:
            sys.exit(f"HTTP {r.status_code}: {r.read().decode()[:300]}")
        for ev in iter_sse(r.iter_lines()):
            render(ev)


if __name__ == "__main__":
    main()

from app.api.sse import format_sse
from scripts.chat_cli import iter_sse


def test_iter_sse_roundtrip_and_ping_ignored():
    evs = [{"seq": 1, "type": "state", "node": "supervisor", "data": {"label": "x"}},
           {"seq": 2, "type": "token", "node": "response", "data": {"text": "hi\nthere"}}]
    raw = ": ping\n\n" + "".join(format_sse(e) for e in evs)
    assert list(iter_sse(raw.split("\n"))) == evs

"""SSE transport and UI state reducer. No Streamlit import."""
import json
from dataclasses import dataclass, field

import httpx


class APIError(Exception):
    pass


def parse_sse(lines):
    data = []
    for line in lines:
        if line.startswith(":"):
            continue
        if not line:
            if data:
                value = json.loads("\n".join(data))
                if not isinstance(value, dict) or "type" not in value or "data" not in value:
                    raise APIError("Invalid event received from server.")
                yield value
                data = []
        elif line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
    if data:
        raise APIError("Stream ended with an incomplete event.")


def stream_chat(base_url, api_key, session_id, message):
    timeout = httpx.Timeout(connect=10, read=270, write=15, pool=10)
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        with client.stream(
            "POST", base_url.rstrip("/") + "/chat/stream",
            headers={"X-API-Key": api_key},
            json={"session_id": session_id, "message": message},
        ) as response:
            if response.status_code != 200:
                if response.status_code == 429:
                    raise APIError(
                        "Rate limit reached. Retry after "
                        + response.headers.get("Retry-After", "a few") + " seconds."
                    )
                messages = {
                    401: "Invalid API key.",
                    403: "Session belongs to another user. Start a new conversation.",
                    422: "The request was rejected as invalid.",
                    503: "The backend is temporarily unavailable.",
                }
                raise APIError(messages.get(
                    response.status_code,
                    f"Backend returned HTTP {response.status_code}.",
                ))
            yield from parse_sse(response.iter_lines())


@dataclass
class Turn:
    draft: str = ""
    final: dict | None = None
    node: str = ""
    label: str = "Connecting"
    events: list = field(default_factory=list)
    retrieval: dict = field(default_factory=dict)
    validation: dict = field(default_factory=dict)
    memory: dict = field(default_factory=dict)
    error: str = ""

    def accept(self, event):
        kind, data = event["type"], event["data"]
        if kind == "token":
            self.draft += str(data.get("text", ""))
            return
        self.events = (self.events + [event])[-150:]
        if event.get("node"):
            self.node = event["node"]
        if kind == "state":
            self.label = data.get("label", "Working")
        elif kind == "generation_start" and data.get("reset"):
            self.draft = ""
        elif kind == "retrieval":
            self.retrieval = data
        elif kind == "validation":
            self.validation = data
        elif kind in ("memory_loaded", "memory_updated"):
            self.memory = data
        elif kind == "error":
            self.error = "The server reported an error."
        elif kind == "final":
            self.final = data
            self.draft = data.get("answer", "")
            if isinstance(data.get("validation"), dict):
                self.validation = dict(data["validation"])
            if data.get("blocked"):
                self.label = "Blocked"
            elif data.get("degraded"):
                self.label = "Complete — degraded"
            else:
                self.label = "Complete"

"""Single source of truth for the graph shape, consumed by builder.py (LangGraph) and by the test runner,
so the edges that are unit tested are the edges that run in production.

guard_input -> (blocked | supervisor)
supervisor  -> (retrieval | research | response)          # chitchat skips retrieval
retrieval   -> response -> validate
research    -> (validate | retrieval)                     # research failure degrades to standard search
validate    -> (response | update_memory)                 # retry loop with guardrail feedback
blocked     -> update_memory -> END
"""
from app.graph import nodes

END = "__end__"
ENTRY = "guard_input"

NODES = {
    "guard_input": nodes.guard_input, "blocked": nodes.blocked, "supervisor": nodes.supervisor,
    "retrieval": nodes.retrieval, "research": nodes.research, "response": nodes.response,
    "validate": nodes.validate, "update_memory": nodes.update_memory,
}


def route_after_guard(state: dict) -> str:
    return "blocked" if state.get("blocked_reason") else "supervisor"


def route_after_supervisor(state: dict) -> str:
    intent = (state.get("route") or {}).get("intent", "knowledge_qa")
    return {"deep_research": "research", "chitchat": "response"}.get(intent, "retrieval")


def route_after_research(state: dict) -> str:
    return "retrieval" if (state.get("research") or {}).get("error") else "validate"


def route_after_validate(state: dict) -> str:
    return "response" if (state.get("validation") or {}).get("retry") else "update_memory"


EDGES = {"retrieval": "response", "response": "validate", "blocked": "update_memory", "update_memory": END}

CONDITIONAL = {
    "guard_input": (route_after_guard, ("supervisor", "blocked")),
    "supervisor": (route_after_supervisor, ("retrieval", "research", "response")),
    "research": (route_after_research, ("validate", "retrieval")),
    "validate": (route_after_validate, ("response", "update_memory")),
}

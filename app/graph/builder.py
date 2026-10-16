"""LangGraph wiring. Thin on purpose: the shape lives in topology.py."""
from app.graph import topology
from app.graph.deps import Deps
from app.graph.runtime import wrap_node
from app.graph.state import ChatState


def build_graph(deps: Deps, checkpointer=None):
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, START, StateGraph

    def target(name: str):
        return END if name == topology.END else name

    g = StateGraph(ChatState)
    for name, fn in topology.NODES.items():
        g.add_node(name, wrap_node(name, fn, deps))
    g.add_edge(START, topology.ENTRY)
    for src, dst in topology.EDGES.items():
        g.add_edge(src, target(dst))
    for src, (router, targets) in topology.CONDITIONAL.items():
        g.add_conditional_edges(src, router, {t: target(t) for t in targets})
    return g.compile(checkpointer=checkpointer or MemorySaver())

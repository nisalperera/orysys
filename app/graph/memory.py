"""Conversation memory design (explained in docs/T2_graph.md).

Three layers, all scoped to one session and one user:
1. Short term: the last WINDOW messages verbatim. Persisted by the LangGraph checkpointer (thread_id = session),
   so memory survives every turn of the session. POC uses MemorySaver, production would use SQLite/Postgres.
2. Rolling summary: when turns fall out of the window an LLM condenses them into `memory_summary`, so long chats
   keep their context at constant prompt size.
3. Episodes + profile: one record per answered question (question, short answer, cited doc ids) and a small user
   profile (recent topics, documents seen). `select_relevant_history` retrieves the most relevant earlier
   episodes by lexical overlap ("relevant historical interactions"). The supervisor uses them to resolve
   follow-ups such as "what about the second incident?".

Safety: blocked inputs are never stored (no memory poisoning). Only answers the user was actually shown
are stored (so memory cannot leak documents above the user's role). Sessions are bound to a user id.
"""
import re

WINDOW = 6          # verbatim messages kept in prompts (3 turns)
MAX_EPISODES = 20
_TOKEN = re.compile(r"[a-z0-9]{4,}")


def recent_history(state: dict, window: int | None = None) -> list[dict]:
    """Messages before the current user question, newest last, capped at the window."""
    w_ = WINDOW if window is None else window
    msgs = list(state.get("messages") or [])
    if msgs and msgs[-1].get("role") == "user":
        msgs = msgs[:-1]
    return msgs[-w_:] if w_ else []


def select_relevant_history(episodes: list[dict], question: str, k: int = 2, min_overlap: float = 0.15) -> list[dict]:
    q = set(_TOKEN.findall(question.lower()))
    scored = []
    for ep in episodes:
        e = set(_TOKEN.findall((ep.get("q", "") + " " + ep.get("a", "")).lower()))
        if not q or not e:
            continue
        s = len(q & e) / len(q | e)
        if s >= min_overlap:
            scored.append((s, ep))
    scored.sort(key=lambda x: -x[0])
    return [ep for _, ep in scored[:k]]


def build_context(state: dict) -> dict:
    question = state.get("question", "")
    return {
        "summary": state.get("memory_summary", ""),
        "recent": recent_history(state),
        "episodes": select_relevant_history(state.get("episodes") or [], question),
        "profile": state.get("profile") or {},
    }


def format_context(ctx: dict) -> str:
    parts = []
    if ctx["summary"]:
        parts.append(f"Summary of earlier conversation:\n{ctx['summary']}")
    if ctx["recent"]:
        parts.append("Recent turns:\n" + "\n".join(f"{m['role']}: {m['content'][:500]}" for m in ctx["recent"]))
    if ctx["episodes"]:
        parts.append("Relevant earlier questions:\n" + "\n".join(
            f"- {e['q'][:200]} (cited: {', '.join(e.get('doc_ids', [])[:4]) or 'none'})" for e in ctx["episodes"]))
    if ctx["profile"].get("recent_topics"):
        parts.append("User recent topics: " + "; ".join(ctx["profile"]["recent_topics"][-3:]))
    return "\n\n".join(parts) or "(no earlier conversation)"


def update_profile(profile: dict, question: str, cited_doc_ids: list[str]) -> dict:
    p = dict(profile or {})
    p["questions_asked"] = p.get("questions_asked", 0) + 1
    p["recent_topics"] = (p.get("recent_topics", []) + [question[:120]])[-5:]
    seen = p.get("docs_seen", [])
    for d in cited_doc_ids:
        if d not in seen:
            seen.append(d)
    p["docs_seen"] = seen[-15:]
    return p


def add_episode(episodes: list[dict], question: str, answer: str, cited_doc_ids: list[str]) -> list[dict]:
    ep = {"q": question[:300], "a": re.sub(r"\s+", " ", answer)[:300], "doc_ids": cited_doc_ids[:6]}
    return ((episodes or []) + [ep])[-MAX_EPISODES:]


def pending_to_summarize(state: dict, window: int | None = None) -> tuple[list[dict], int]:
    """Messages that fell out of the window and are not summarised yet, plus the new `summarized_upto`.
    Summarises whole turns only (even count) so a question is never separated from its answer."""
    w_ = WINDOW if window is None else window
    msgs = state.get("messages") or []
    upto = state.get("summarized_upto", 0)
    end = len(msgs) - w_
    end -= end % 2
    return (msgs[upto:end], end) if end - upto >= 2 else ([], upto)


def fallback_summary(previous: str, turns: list[dict], limit: int = 900) -> str:
    """Deterministic summary used when the summariser LLM fails."""
    lines = [f"{m['role']}: {re.sub(chr(10), ' ', m['content'])[:140]}" for m in turns]
    return (previous + "\n" + "\n".join(lines)).strip()[-limit:]

"""LangGraph node functions. Each node is `async (state, deps) -> partial state update`.

Agents (mapped to the brief): supervisor (intent, routing), retrieval agent (hybrid RAG), research agent (RLM),
response agent (final answer), plus guard_input / validate / update_memory control nodes.
Nodes never read the user's role from model output: identity comes from `state["user_id"]` (server set).
"""
import asyncio
import json
import logging
from typing import Any

from pydantic import ValidationError

from app.graph import memory
from app.graph.decision import SupervisorDecision, apply_policy, heuristic_decision
from app.graph.deps import Deps
from app.graph.prompts import CHITCHAT_SYSTEM, RESPONSE_SYSTEM, SUMMARY_SYSTEM, SUPERVISOR_SYSTEM
from app.graph.validators import (ID_RX, build_feedback, strip_invalid_citations, validate_answer)
from app.observability import traceable
from app.retrieval.schemas import SearchRequest
from app.rlm.jsonutil import extract_json
from app.rlm.safety import neutralize_injection
from app.security.input_guard import check_user_input

log = logging.getLogger("graph")

BLOCKED_MESSAGE = ("I can't help with that request. I can answer questions about {bank} policies, runbooks, incident "
                   "reports, architecture and product documents that your role can access. Please rephrase your question.")
SECRET_MESSAGE = "I can't share that response because it may contain sensitive information. Please rephrase your question."
NO_RESULTS_MESSAGE = ("I could not find relevant information in the documents available to you for that question. "
                      "Try rephrasing, or name the document, incident or time period you are interested in.")
SEARCH_DOWN_MESSAGE = "I'm unable to search the document store right now. Please try again in a moment."
LLM_DOWN_MESSAGE = "I'm unable to generate an answer right now. Please try again in a moment."
_RESET = {"route": {}, "policy_notes": [], "retrieved": [], "retrieval_meta": {}, "research": {}, "evidence_ids": [],
          "analysis_text": "", "draft_answer": "", "attempts": 0, "validation": {}, "final_answer": "", "citations": [],
          "blocked_reason": "", "node_errors": []}


# ------------------------------------------------------------------ guard_input
async def guard_input(state: dict, deps: Deps) -> dict:
    rid = state.get("request_id", "-")
    res = check_user_input(state.get("question"))
    if not res.ok:
        deps.emit(rid, "input_guard", "guard_input", ok=False, category=res.category, reason=res.reason)
        log.warning("input blocked", extra={"extra_fields": {"category": res.category, "user_id": state.get("user_id")}})
        return {**_RESET, "question": "", "blocked_reason": res.category,
                "final_answer": BLOCKED_MESSAGE.format(bank=deps.bank_name)}
    deps.emit(rid, "input_guard", "guard_input", ok=True)
    deps.emit(rid, "memory_loaded", "guard_input", messages=len(state.get("messages") or []),
              summary_chars=len(state.get("memory_summary", "")), episodes=len(state.get("episodes") or []))
    return {**_RESET, "question": res.text, "messages": [{"role": "user", "content": res.text}]}


async def blocked(state: dict, deps: Deps) -> dict:
    deps.emit(state.get("request_id", "-"), "generation_start", "blocked", mode="blocked", attempt=1, reset=True)
    return {"draft_answer": state.get("final_answer", ""), "citations": []}


# ------------------------------------------------------------------ supervisor
async def supervisor(state: dict, deps: Deps) -> dict:
    rid, q = state.get("request_id", "-"), state["question"]
    user = deps.users[state["user_id"]]
    ctx = memory.build_context(state)
    system = SUPERVISOR_SYSTEM.format(bank=deps.bank_name, today=deps.today().isoformat(), role=user.role.value)
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": f"Context:\n{memory.format_context(ctx)}\n\nUser message:\n{q}"}]
    source = "llm"
    try:
        decision = SupervisorDecision.model_validate(extract_json(await deps.llm(messages)))
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001  LLM down or invalid JSON: degrade to heuristics
        decision, source = heuristic_decision(q), "heuristic"
        deps.emit(rid, "policy", "supervisor", note=f"supervisor LLM unavailable or invalid ({type(exc).__name__}), "
                                                    "heuristic routing used")
    decision, user_notes, internal = apply_policy(decision, user.role, q, deps.departments(user))
    for note in user_notes + internal:
        deps.emit(rid, "policy", "supervisor", note=note)
    deps.emit(rid, "routing", "supervisor", intent=decision.intent, standalone_query=decision.standalone_query,
              filters={k: v for k, v in decision.model_dump().items()
                       if k in ("document_types", "date_from", "date_to", "department") and v},
              source=source, reason=decision.reason)
    return {"route": decision.model_dump(), "policy_notes": user_notes}


# ------------------------------------------------------------------ retrieval agent
async def _search(deps: Deps, user: Any, req: SearchRequest):
    @traceable(name="hybrid_search", run_type="retriever")
    async def run(query: str, filters: dict, role: str):
        return await asyncio.wait_for(deps.search(user, req), deps.search_timeout)

    try:
        return await run(req.query, req.model_dump(mode="json", exclude={"query"}, exclude_none=True), user.role.value)
    except Exception as exc:  # noqa: BLE001  tracing must never break retrieval
        if not type(exc).__module__.startswith("langsmith"):
            raise
        log.warning("LangSmith tracing error, searching untraced: %s", exc)
        return await asyncio.wait_for(deps.search(user, req), deps.search_timeout)


async def retrieval(state: dict, deps: Deps) -> dict:
    rid, route = state.get("request_id", "-"), state.get("route") or {}
    user = deps.users[state["user_id"]]
    q = (route.get("standalone_query") or state["question"])[:1000]
    filters = {k: route[k] for k in ("document_types", "date_from", "date_to", "department") if route.get(k)}
    deps.emit(rid, "retrieval_start", "retrieval", query=q, filters=filters)
    try:
        req = SearchRequest(query=q, top_k=8, **filters)
    except ValidationError:
        req = SearchRequest(query=state["question"][:1000], top_k=8)
        deps.emit(rid, "policy", "retrieval", note="invalid router output was discarded, original question used unfiltered")
    try:
        res = await _search(deps, user, req)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001  RetrievalError, timeout, anything
        meta = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"[:300]}
        log.warning("retrieval failed: %s", meta["error"])
        deps.emit(rid, "retrieval", "retrieval", **meta)
        return {"retrieved": [], "retrieval_meta": meta}
    hits = [h.model_dump() for h in res.hits]
    meta = {"status": "ok", "hits": len(hits), "namespaces": res.namespaces_searched,
            "chunks": [{"id": h["chunk_id"], "score": round(h["score"], 3), "section": h["section"]} for h in hits],
            "failed_namespaces": res.failed_namespaces, "degraded": res.degraded, "degraded_reasons": res.degraded_reasons,
            "no_relevant_results": res.no_relevant_results, "dropped_by_cap": res.dropped_by_doc_cap,
            "dropped_below_min": res.dropped_below_min_score, "alpha": res.alpha, "embed_ms": res.embed_ms,
            "query_ms": res.query_ms, "doc_ids": list(dict.fromkeys(h["doc_id"] for h in hits))}
    deps.emit(rid, "retrieval", "retrieval", **meta)
    return {"retrieved": hits, "retrieval_meta": meta}


# ------------------------------------------------------------------ research agent (RLM)
async def research(state: dict, deps: Deps) -> dict:
    rid, route = state.get("request_id", "-"), state.get("route") or {}
    user = deps.users[state["user_id"]]
    q = route.get("standalone_query") or state["question"]
    deps.emit(rid, "research_start", "research", query=q)

    def forward(ev: dict) -> None:
        data = {k: v for k, v in ev.items() if k not in ("agent", "stage", "type")}
        deps.emit(rid, f"rlm.{ev.get('type', 'event')}", "research", **data)

    try:
        res = await asyncio.wait_for(deps.make_engine(forward).run(user, q), deps.research_timeout)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001  degrade: fall back to the standard search path
        err = f"{type(exc).__name__}: {exc}"[:300]
        log.warning("research failed: %s", err)
        deps.emit(rid, "policy", "research", note=f"deep research failed ({err}), falling back to standard search")
        return {"research": {"error": err}, "route": {**route, "intent": "knowledge_qa"},
                "policy_notes": (state.get("policy_notes") or []) + ["Deep research was unavailable, so a standard search was used instead."]}
    meta = res.model_dump(exclude={"analysis", "answer"})
    return {"research": meta, "draft_answer": res.answer, "evidence_ids": list(dict.fromkeys(res.relevant_doc_ids)),
            "analysis_text": json.dumps(res.analysis, default=str), "attempts": 1}


# ------------------------------------------------------------------ response agent
def _excerpts(evidence: list[dict]) -> str:
    parts = []
    for h in evidence:
        clean, _ = neutralize_injection(h["text"])
        parts.append(f'<excerpt id="{h["chunk_id"]}" title="{h["title"]}" date="{h["created_date"]}">\n{clean}\n</excerpt>')
    return "\n".join(parts)


def _extractive_fallback(evidence: list[dict]) -> str:
    lines = ["I couldn't generate a full answer right now. These are the most relevant excerpts:"]
    for h in evidence[:3]:
        body = " ".join(h["text"].split("\n", 1)[-1].split())[:280]
        lines.append(f"- {body} [{h['chunk_id']}]")
    return "\n".join(lines)


async def response(state: dict, deps: Deps) -> dict:
    rid, route = state.get("request_id", "-"), state.get("route") or {}
    intent, attempt = route.get("intent", "knowledge_qa"), state.get("attempts", 0) + 1
    evidence = state.get("retrieved") or []
    ctx = memory.format_context(memory.build_context(state))
    question = route.get("standalone_query") or state["question"]

    if intent == "chitchat":
        mode = "chitchat"
        messages = [{"role": "system", "content": CHITCHAT_SYSTEM.format(bank=deps.bank_name)},
                    {"role": "user", "content": f"Context:\n{ctx}\n\nUser message:\n{state['question']}"}]
    elif not evidence:
        meta = state.get("retrieval_meta") or {}
        text = SEARCH_DOWN_MESSAGE if meta.get("status") == "failed" else NO_RESULTS_MESSAGE
        deps.emit(rid, "generation_start", "response", mode="no_evidence", attempt=attempt, reset=True)
        return {"draft_answer": text, "attempts": attempt}
    else:
        mode = "grounded"
        feedback = (state.get("validation") or {}).get("feedback", "") if attempt > 1 else ""
        retry = f"\n\nYour previous answer was rejected: {feedback}. Fix this and answer again." if feedback else ""
        messages = [{"role": "system", "content": RESPONSE_SYSTEM.format(bank=deps.bank_name)},
                    {"role": "user", "content": f"Context:\n{ctx}\n\nQuestion:\n{question}\n\n"
                                                f"Excerpts:\n{_excerpts(evidence)}{retry}"}]
    deps.emit(rid, "generation_start", "response", mode=mode, attempt=attempt, reset=True)
    parts: list[str] = []
    try:
        async for tok in deps.llm_stream(messages):
            parts.append(tok)
            deps.emit(rid, "token", "response", text=tok)
        return {"draft_answer": "".join(parts).strip(), "attempts": attempt}
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001  LLM failure: extractive fallback, never a crash
        log.warning("response generation failed: %s: %s", type(exc).__name__, exc)
        deps.emit(rid, "generation_failed", "response", error=f"{type(exc).__name__}: {exc}"[:300])
        text = _extractive_fallback(evidence) if evidence else LLM_DOWN_MESSAGE
        return {"draft_answer": text, "attempts": attempt,
                "node_errors": (state.get("node_errors") or []) + ["response: llm_failed"]}


# ------------------------------------------------------------------ validate (guardrails)
def _build_citations(final: str, evidence: list[dict], evidence_ids: list[str], research_mode: bool) -> list[dict]:
    cited = {i.split("#")[0] for i in ID_RX.findall(final)}
    if research_mode:
        return [{"doc_id": d} for d in evidence_ids if d in cited or not cited]
    by_doc: dict[str, dict] = {}
    for h in evidence:
        if cited and h["doc_id"] not in cited:
            continue
        c = by_doc.setdefault(h["doc_id"], {"doc_id": h["doc_id"], "title": h["title"], "document_type": h["document_type"],
                                            "created_date": h["created_date"], "chunks": [], "top_score": h["score"]})
        c["chunks"].append(h["chunk_id"])
    return list(by_doc.values())


async def validate(state: dict, deps: Deps) -> dict:
    rid, route = state.get("request_id", "-"), state.get("route") or {}
    draft, attempt = state.get("draft_answer", ""), state.get("attempts", 1)
    research_mode = route.get("intent") == "deep_research" and bool(state.get("research")) and not (state.get("research") or {}).get("error")
    evidence = state.get("retrieved") or []
    if research_mode:
        docs, chunks, ev_text = set(state.get("evidence_ids") or []), set(), state.get("analysis_text", "")
        has_evidence = bool(docs)
    else:
        docs = {h["doc_id"] for h in evidence}
        chunks = {h["chunk_id"] for h in evidence}
        ev_text, has_evidence = "\n".join(h["text"] for h in evidence), bool(evidence)
    user_ids = set(ID_RX.findall(state.get("question", "")))  # ids the user typed are not hallucinations
    docs |= {i.split("#")[0] for i in user_ids}
    chunks |= {i for i in user_ids if "#" in i}

    result = validate_answer(draft, docs, chunks, ev_text, has_evidence)
    codes = {i["code"] for i in result.issues}
    if not result.ok and not research_mode and attempt < deps.max_attempts and "secret_leak" not in codes:
        deps.emit(rid, "validation", "validate", ok=False, action="retry", attempt=attempt, issues=result.issues)
        return {"validation": {"ok": False, "retry": True, "issues": result.issues, "feedback": build_feedback(result.issues)}}

    if "secret_leak" in codes:
        log.error("secret leak blocked in answer", extra={"extra_fields": {"user_id": state.get("user_id")}})
        final, action = SECRET_MESSAGE, "replaced"
    else:
        final = strip_invalid_citations(draft, docs, chunks)
        action = "sanitized" if final != draft else "passed"
        if has_evidence and not ID_RX.search(final) and "could not find" not in final.lower() and not research_mode:
            top = list(dict.fromkeys(h["chunk_id"] for h in evidence))[:3]
            final += "\n\nSources: " + ", ".join(f"[{c}]" for c in top)
            action = "sanitized"
    notes = state.get("policy_notes") or []
    if notes:
        final += "\n\n" + " ".join(notes)
    degraded = bool(state.get("node_errors")) or bool((state.get("retrieval_meta") or {}).get("degraded")) \
        or bool((state.get("research") or {}).get("degraded"))
    deps.emit(rid, "validation", "validate", ok=result.ok, action=action, attempt=attempt, issues=result.issues)
    return {"validation": {"ok": result.ok, "retry": False, "issues": result.issues, "action": action, "degraded": degraded},
            "final_answer": final, "citations": _build_citations(final, evidence, state.get("evidence_ids") or [], research_mode)}


# ------------------------------------------------------------------ memory update
async def update_memory(state: dict, deps: Deps) -> dict:
    rid = state.get("request_id", "-")
    if state.get("blocked_reason"):
        deps.emit(rid, "memory_updated", "update_memory", skipped=True, reason="blocked input is never stored")
        return {}
    final, q = state.get("final_answer", ""), state.get("question", "")
    cited = [c["doc_id"] for c in state.get("citations") or []]
    assistant = {"role": "assistant", "content": final[:4000]}
    projected = {**state, "messages": (state.get("messages") or []) + [assistant]}
    to_sum, upto = memory.pending_to_summarize(projected)
    summary, summarized = state.get("memory_summary", ""), False
    if to_sum:
        turns = "\n".join(f"{m['role']}: {m['content'][:600]}" for m in to_sum)
        try:
            summary = (await deps.llm([{"role": "system", "content": SUMMARY_SYSTEM},
                                       {"role": "user", "content": f"Earlier summary:\n{summary}\n\nNew turns:\n{turns}"}])).strip()[:1200]
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            summary = memory.fallback_summary(summary, to_sum)
        summarized = True
    profile = memory.update_profile(state.get("profile") or {}, q, cited)
    episodes = memory.add_episode(state.get("episodes") or [], q, final, cited)
    deps.emit(rid, "memory_updated", "update_memory", turns=len(projected["messages"]) // 2, summarized=summarized,
              summary_chars=len(summary), episodes=len(episodes), recent_topics=profile["recent_topics"][-2:])
    return {"messages": [assistant], "memory_summary": summary, "summarized_upto": upto, "profile": profile,
            "episodes": episodes}

"""Recursive Language Model engine (research agent core).

Flow (each step emits an activity event):
  1 explore    catalog stats only, no document content reaches an LLM
  2 plan       LLM writes a Python search plan, parsed via ast (plan.py), fallback plan if invalid
  3 select     plain Python filters the catalog (type, date, topic, RBAC)
  4 batch      split selected documents into small batches
  5 analyse    one sub-agent per batch, in parallel, over targeted sections retrieved from Pinecone
               (doc_id filtered hybrid search). Oversized batches are split and analysed recursively.
  6 aggregate  Python analysis tool computes counts and totals, hierarchical LLM reduce writes the answer

Failure behaviour: a failed batch is reported and skipped, a failed reduce falls back to a deterministic
summary built from the analysis. The result always says what is missing.
LLM and retriever are injected: any OpenAI-compatible provider (OpenRouter, vLLM) works.
"""
import asyncio
import inspect
import json
import logging
import re
from datetime import date
from typing import Any, Awaitable, Callable, Optional

from pydantic import ValidationError

from app.auth.models import User
from app.retrieval.schemas import Hit, SearchRequest
from app.rlm.catalog import Catalog
from app.rlm.errors import is_permanent
from app.rlm.evidence_policy import supported_findings
from app.reliability import task_for_user, render_extreme
from app.rlm.guard import reconcile_select
from app.rlm.jsonutil import extract_json, strip_think
from app.rlm.models import BatchResult, DocFinding, DocRef, RLMConfig, RLMResult
from app.rlm.plan import Plan, PlanError, DOC_TYPES, default_plan, parse_plan
from app.rlm.prompts import (ANALYZE_SYSTEM, PARTIAL_SYSTEM, PLAN_RETRY, PLAN_SYSTEM, REDUCE_SYSTEM)
from app.rlm.safety import neutralize_injection
from app.tools.python_analysis import analyze_findings, extract_facts

log = logging.getLogger("rlm")

LLMFn = Callable[[list[dict]], Awaitable[str]]
EmitFn = Callable[[dict], Any]
_DOC_ID_RX = re.compile(r"\b[A-Z]{2,5}-(?:\d{4}-)?\d{3}\b")


class LLMCallError(Exception):
    pass


class _Run:
    def __init__(self, concurrency: int):
        self.sem = asyncio.Semaphore(concurrency)
        self.max_depth = 0
        self.neutralized = 0
        self.batches = 0
        self.reasons: list[str] = []


def _chunks(items: list, n: int) -> list[list]:
    return [items[i:i + n] for i in range(0, len(items), n)]


class RLMEngine:
    def __init__(self, llm: LLMFn, retriever: Any, catalog: Catalog, config: Optional[RLMConfig] = None,
                 emit: Optional[EmitFn] = None, sanitize: Callable[[str], tuple[str, int]] = neutralize_injection):
        self.llm, self.retriever, self.catalog = llm, retriever, catalog
        self.cfg, self._emit_cb, self.sanitize = config or RLMConfig(), emit, sanitize

    async def _emit(self, type_: str, **data) -> None:
        ev = {"agent": "research", "stage": "rlm", "type": type_, **data}
        log.info("rlm.%s", type_, extra={"extra_fields": data})
        if self._emit_cb:
            try:
                r = self._emit_cb(ev)
                if inspect.isawaitable(r):
                    await r
            except Exception:  # noqa: BLE001  (UI problems must never break the run)
                log.exception("emit callback failed")

    async def _call_llm(self, messages: list[dict]) -> str:
        last: Optional[Exception] = None
        for attempt in range(self.cfg.llm_retries + 1):
            try:
                return strip_think(await asyncio.wait_for(self.llm(messages), self.cfg.llm_timeout_sec))
            except Exception as exc:  # noqa: BLE001
                last = exc
                if is_permanent(exc):
                    break
                if attempt < self.cfg.llm_retries:
                    await asyncio.sleep(self.cfg.retry_backoff_sec * (attempt + 1))
        raise LLMCallError("Language model request failed; analysis could not be completed.") from last

    # ---------------------------------------------------------------- plan
    async def _make_plan(self, user: User, question: str, today: date, run: _Run) -> Plan:
        system = PLAN_SYSTEM.format(types=sorted(DOC_TYPES), max_batch=self.cfg.max_batch_size, today=today.isoformat(),
                                    stats=json.dumps(self.catalog.stats(user)))
        messages = [{"role": "system", "content": system}, {"role": "user", "content": question}]
        error = "no attempt"
        for attempt in range(2):
            try:
                raw = await self._call_llm(messages)
                plan = parse_plan(raw, self.cfg.max_batch_size)
                await self._emit("plan_generated", source="llm", code=plan.code)
                return plan
            except (PlanError, LLMCallError) as exc:
                error = str(exc)
                await self._emit("plan_rejected", attempt=attempt + 1, error=error)
                if isinstance(exc, LLMCallError):
                    break
                messages += [{"role": "assistant", "content": raw},
                             {"role": "user", "content": PLAN_RETRY.format(error=error)}]
        run.reasons.append(f"LLM plan unavailable ({error}); used fallback plan")
        plan = default_plan(question, today, self.cfg.default_batch_size)
        await self._emit("plan_generated", source="fallback", code=plan.code)
        return plan

    # ---------------------------------------------------------------- main
    async def run(self, user: User, question: str) -> RLMResult:
        run = _Run(self.cfg.concurrency)
        run.question = question
        today = self.cfg.today or date.today()

        await self._emit("explore", stats=self.catalog.stats(user))
        plan = await self._make_plan(user, question, today, run)

        select_args, adjustments = reconcile_select(
            plan.select.model_dump(), question, set(self.catalog.stats(user)["by_department"]))
        for note in adjustments:
            await self._emit("plan_adjusted", note=note)
        docs = self.catalog.select(user, **select_args)
        truncated = len(docs) > self.cfg.max_docs
        docs = docs[: self.cfg.max_docs]
        await self._emit("select", matched=len(docs), truncated=truncated, doc_ids=[d.doc_id for d in docs])
        if truncated:
            run.reasons.append(f"selection truncated to {self.cfg.max_docs} documents")
        if not docs:
            return self._result("No accessible documents match this request.", plan, docs, truncated, [], {}, run, [])

        groups = _chunks(docs, plan.batch_size)
        run.batches = len(groups)
        await self._emit("batches", count=len(groups), sizes=[len(g) for g in groups])
        batch_results: list[BatchResult] = [
            r for sub in await asyncio.gather(*(self._run_batch(user, g, i, plan, run) for i, g in enumerate(groups)))
            for r in sub]

        failed = [b.batch_id for b in batch_results if b.error]
        for b in batch_results:
            run.reasons += [f"{b.batch_id}: {w_}" for w_ in b.warnings]
            if b.error:
                run.reasons.append(f"batch {b.batch_id} failed: {b.error}")
        findings = [f for b in batch_results for f in b.findings if f.relevant]
        analysed = {f.doc_id for b in batch_results for f in b.findings}
        for d in docs:
            if d.doc_id not in analysed and not any(d.doc_id in b.doc_ids and b.error for b in batch_results):
                run.reasons.append(f"{d.doc_id}: no evidence retrieved")

        meta = {d.doc_id: {"created_date": d.created_date, **extract_facts(self.catalog.body(d.doc_id))} for d in docs}
        analysis = analyze_findings([f.model_dump() for f in findings], meta)
        await self._emit("analysis", relevant=len(findings), recurring=analysis["recurring"])

        if not findings and docs and analysed:
            run.reasons.append("All selected documents classified irrelevant after recheck; completeness not established")
            await self._emit("relevance_warning", selected=len(docs), analysed=len(analysed))
        if not findings:
            if batch_results and all(batch.error for batch in batch_results):
                msg = "The documents could not be analysed because a required service failed. Please try again."
            elif docs and analysed:
                msg = "I could not establish relevance for the selected documents after a recheck. This analysis is incomplete; please retry or refine the request."
            else:
                msg = "No relevant documents were found for this request."
            if failed:
                msg += " Some batches failed, so the search may be incomplete."
            return self._result(msg, plan, docs, truncated, failed, analysis, run, findings)

        answer = await self._reduce(question, plan, findings, analysis, run, meta, failed)
        return self._result(answer, plan, docs, truncated, failed, analysis, run, findings)

    def _result(self, answer, plan, docs, truncated, failed, analysis, run, findings) -> RLMResult:
        allowed = {d.doc_id for d in docs}
        unverified = sorted(set(_DOC_ID_RX.findall(answer)) - allowed)
        if unverified:
            run.reasons.append(f"unverified citations in answer: {unverified}")
        return RLMResult(
            answer=answer, degraded=bool(run.reasons or failed), degraded_reasons=run.reasons,
            plan_source=plan.source, plan_code=plan.code, docs_considered=len(docs), docs_truncated=truncated,
            batches=run.batches, max_depth_reached=run.max_depth, failed_batches=failed,
            relevant_doc_ids=sorted({f.doc_id for f in findings}), analysis=analysis,
            unverified_citations=unverified, neutralized_snippets=run.neutralized)

    # ---------------------------------------------------------------- sub-agents
    async def _run_batch(self, user: User, group: list[DocRef], idx: int, plan: Plan, run: _Run) -> list[BatchResult]:
        batch_id = f"b{idx}"
        ids = [d.doc_id for d in group]
        await self._emit("batch_start", batch_id=batch_id, doc_ids=ids)
        try:
            req = SearchRequest(query=plan.analyze_question[:1000], top_k=min(20, 6 * len(group)),
                                document_types=sorted({d.document_type for d in group}), doc_ids=ids)
            async with run.sem:
                retrieved = await self.retriever.search(user, req)
        except Exception as exc:  # noqa: BLE001  (RetrievalError, validation, anything)
            log.warning("batch retrieval failed: %s", type(exc).__name__)
            await self._emit("batch_failed", batch_id=batch_id, error="retrieval_unavailable")
            return [BatchResult(batch_id=batch_id, depth=0, doc_ids=ids, error="retrieval_unavailable")]
        await self._emit("retrieval", batch_id=batch_id, hits=len(retrieved.hits), degraded=retrieved.degraded)
        results = await self._analyze_hits(plan, group, retrieved.hits, 0, batch_id, run)
        if retrieved.hits and not any(f.relevant for b in results for f in b.findings) and not any(b.error for b in results):
            await self._emit("relevance_retry", batch_id=batch_id)
            corrected = plan.model_copy(update={"analyze_question": task_for_user(run.question)})
            results = await self._analyze_hits(corrected, group, retrieved.hits, 0, batch_id, run)
        if retrieved.degraded:
            for result in results:
                result.warnings.append("Retrieval was degraded; evidence coverage may be incomplete")
        await self._emit("batch_done", batch_id=batch_id, findings=sum(len(r.findings) for r in results),
                         sub_batches=len(results))
        return results

    async def _analyze_hits(self, plan: Plan, docs: list[DocRef], hits: list[Hit], depth: int, batch_id: str,
                            run: _Run) -> list[BatchResult]:
        run.max_depth = max(run.max_depth, depth)
        size = sum(len(h.text) for h in hits)
        if size > self.cfg.context_char_budget and len(docs) > 1 and depth < self.cfg.max_depth:
            mid = len(docs) // 2
            halves = [docs[:mid], docs[mid:]]
            await self._emit("recurse", batch_id=batch_id, depth=depth + 1, evidence_chars=size,
                             split=[[d.doc_id for d in h] for h in halves])
            subs = await asyncio.gather(*(
                self._analyze_hits(plan, h, [x for x in hits if x.doc_id in {d.doc_id for d in h}],
                                   depth + 1, f"{batch_id}.{i}", run) for i, h in enumerate(halves)))
            return [r for s in subs for r in s]
        return [await self._analyze_leaf(plan, docs, hits, depth, batch_id, run)]

    def _render(self, docs: list[DocRef], hits: list[Hit], run: _Run) -> tuple[str, set[str]]:
        by_doc: dict[str, list[Hit]] = {d.doc_id: [] for d in docs}
        for h in hits:
            by_doc.setdefault(h.doc_id, []).append(h)
        parts, ids, used = [], set(), 0
        for d in docs:
            parts.append(f'<document id="{d.doc_id}" title="{d.title}" date="{d.created_date}">')
            for h in by_doc.get(d.doc_id, []):
                clean, n = self.sanitize(h.text)
                run.neutralized += n
                if used + len(clean) > self.cfg.context_char_budget:
                    break
                used += len(clean)
                ids.add(h.chunk_id)
                parts.append(f"[{h.chunk_id}] {clean}")
            parts.append("</document>")
        return "\n".join(parts), ids

    async def _analyze_leaf(self, plan: Plan, docs: list[DocRef], hits: list[Hit], depth: int, batch_id: str,
                            run: _Run) -> BatchResult:
        ids = [d.doc_id for d in docs]
        res = BatchResult(batch_id=batch_id, depth=depth, doc_ids=ids)
        if not hits:
            res.warnings.append("no retrievable sections for these documents")
            return res
        context, valid_chunks = self._render(docs, hits, run)
        if len(valid_chunks) < len(hits):
            res.warnings.append("evidence truncated to context budget")
        messages = [{"role": "system", "content": ANALYZE_SYSTEM},
                    {"role": "user", "content": f"{task_for_user(run.question)}\nExtraction focus: {plan.analyze_question}\n\n{context}"}]
        parsed = None
        for attempt in range(2):
            try:
                async with run.sem:
                    raw = await self._call_llm(messages)
                parsed = extract_json(raw)
                break
            except LLMCallError as exc:
                res.error = str(exc)
                return res
            except ValueError:
                messages += [{"role": "assistant", "content": raw},
                             {"role": "user", "content": "Invalid JSON. Return only the JSON object."}]
        if parsed is None:
            res.error = "sub-agent returned invalid JSON twice"
            return res
        allowed = set(ids)
        for item in parsed.get("findings", []) if isinstance(parsed.get("findings"), list) else []:
            try:
                f = DocFinding.model_validate(item)
            except ValidationError:
                continue
            if f.doc_id not in allowed:  # hallucinated document id
                res.warnings.append(f"dropped finding for unknown doc {f.doc_id}")
                continue
            supported, warnings = supported_findings([f], valid_chunks, hits)
            res.warnings.extend(warnings)
            res.findings.extend(supported)
        return res

    # ---------------------------------------------------------------- reduce
    async def _reduce(self, question: str, plan: Plan, findings: list[DocFinding], analysis: dict, run: _Run,
                      meta: dict, failed: list[str]) -> str:
        deterministic = render_extreme(question, analysis) if not failed and not run.reasons else None
        if deterministic is not None:
            await self._emit("deterministic_comparison", records=len(analysis.get("incidents", [])))
            return deterministic
        items = [f"[{f.doc_id}] ({meta.get(f.doc_id, {}).get('created_date', '?')}) cause={f.root_cause or 'n/a'}; "
                 f"service={f.service or 'n/a'}; {f.summary}" for f in findings]
        rounds = 0
        while len(items) > self.cfg.fan_in and rounds < self.cfg.max_reduce_rounds:
            groups = _chunks(items, self.cfg.fan_in)
            await self._emit("reduce_round", round=rounds + 1, groups=len(groups))
            items = await asyncio.gather(*(self._partial(g, run) for g in groups))
            rounds += 1
        gaps = f"\nBatches that failed: {failed}" if failed else ""
        user_msg = (f"Question: {question}\nFocus: {plan.reduce_question}\n\nComputed analysis (authoritative):\n"
                    f"{json.dumps(analysis, indent=1)}\n\nFindings:\n" + "\n".join(items) + gaps)
        await self._emit("reduce", findings=len(findings))
        try:
            async with run.sem:
                return await self._call_llm([{"role": "system", "content": REDUCE_SYSTEM},
                                             {"role": "user", "content": user_msg}])
        except LLMCallError as exc:
            run.reasons.append(f"final aggregation LLM failed ({exc}); deterministic summary used")
            await self._emit("reduce_fallback", error=str(exc))
            return self._fallback_answer(analysis, failed)

    async def _partial(self, group: list[str], run: _Run) -> str:
        try:
            async with run.sem:
                return await self._call_llm([{"role": "system", "content": PARTIAL_SYSTEM},
                                             {"role": "user", "content": "\n".join(group)}])
        except LLMCallError:
            return "\n".join(group)[:1500]  # keep raw findings rather than lose them

    @staticmethod
    def _fallback_answer(analysis: dict, failed: list[str]) -> str:
        lines = [f"Analysed {analysis['total_documents']} relevant documents (automatic summary, the language model "
                 f"was unavailable)."]
        for c in analysis["by_root_cause"]:
            ids = ", ".join(f"[{i}]" for i in c["doc_ids"])
            lines.append(f"- {c['root_cause']}: {c['count']} occurrence(s), {c['downtime_minutes']} min downtime, {ids}")
        if failed:
            lines.append(f"Note: batches {failed} failed, results may be incomplete.")
        return "\n".join(lines)

# acceptance-reliability-v1

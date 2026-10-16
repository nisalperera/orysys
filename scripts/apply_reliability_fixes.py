# Validate every anchor before writing. Backups: *.reliability.bak.
from pathlib import Path
import ast
MARKER='# acceptance-reliability-v1'

def replace_once(text,old,new,label):
    if old not in text: raise SystemExit(f'Anchor missing: {label}. No files changed.')
    return text.replace(old,new,1)
def replace_fn(text,name,new):
    node=next(x for x in ast.parse(text).body if isinstance(x,ast.FunctionDef) and x.name==name)
    lines=text.splitlines(keepends=True)
    return ''.join(lines[:node.lineno-1])+new+'\n\n'+''.join(lines[node.end_lineno:])

def build(root):
    paths=['app/rlm/executor.py','app/rlm/plan.py','app/rlm/prompts.py','app/graph/nodes.py',
           'app/graph/state.py','app/graph/validators.py','scripts/run_acceptance.py']
    out={p:(root/p).read_text() for p in paths}
    if all(MARKER in t for t in out.values()): return {}
    if any(MARKER in t for t in out.values()): raise SystemExit('Partial patch detected; inspect backups.')
    def edit(p,old,new): out[p]=replace_once(out[p],old,new,p+' / '+old[:55])
    p='app/rlm/plan.py'
    edit(p,'    questions = []\n','    questions = []\n    from app.reliability import placeholder_task\n')
    edit(p,'        questions.append(q)\n',
         '        if placeholder_task(q):\n            raise PlanError("Write task-specific questions, not example placeholders")\n        questions.append(q)\n')
    p='app/rlm/executor.py'
    edit(p,'from app.rlm.catalog import Catalog\n','from app.rlm.catalog import Catalog\nfrom app.reliability import task_for_user, render_extreme\n')
    edit(p,'        run = _Run(self.cfg.concurrency)\n','        run = _Run(self.cfg.concurrency)\n        run.question = question\n')
    edit(p,'f"Task: {plan.analyze_question}\\n\\n{context}"',
         'f"{task_for_user(run.question)}\\nExtraction focus: {plan.analyze_question}\\n\\n{context}"')
    edit(p,'        await self._emit("batch_done", batch_id=batch_id, findings=sum(len(r.findings) for r in results),',
         '        if retrieved.hits and not any(f.relevant for b in results for f in b.findings) and not any(b.error for b in results):\n'
         '            await self._emit("relevance_retry", batch_id=batch_id)\n'
         '            corrected = plan.model_copy(update={"analyze_question": task_for_user(run.question)})\n'
         '            results = await self._analyze_hits(corrected, group, retrieved.hits, 0, batch_id, run)\n'
         '        await self._emit("batch_done", batch_id=batch_id, findings=sum(len(r.findings) for r in results),')
    edit(p,'        if not findings:\n',
         '        if not findings and docs and analysed:\n'
         '            run.reasons.append("All selected documents classified irrelevant after recheck; completeness not established")\n'
         '            await self._emit("relevance_warning", selected=len(docs), analysed=len(analysed))\n'
         '        if not findings:\n')
    edit(p,'            msg = "No relevant documents were found for this request."\n',
         '            msg = "No relevant documents were found for this request."\n'
         '            if docs and analysed:\n'
         '                msg = "I could not establish relevance for the selected documents after a recheck. This analysis is incomplete; please retry or refine the request."\n')
    edit(p,'        items = [f"[{f.doc_id}]',
         '        deterministic = render_extreme(question, analysis) if not failed and not run.reasons else None\n'
         '        if deterministic is not None:\n'
         '            await self._emit("deterministic_comparison", records=len(analysis.get("incidents", [])))\n'
         '            return deterministic\n'
         '        items = [f"[{f.doc_id}]')
    p='app/rlm/prompts.py'
    out[p]=out[p].replace('what each batch must extract','extract relevance, root cause, service and evidence for each payment incident')
    out[p]=out[p].replace('how to combine the findings','summarize payment outages and group recurring root causes').replace('[DOC_ID]','[INC-2025-031]')
    p='app/graph/state.py'
    edit(p,'    question: str\n','    question: str\n    research_scope: dict\n')
    p='app/graph/nodes.py'
    edit(p,'from app.graph import memory\n',
         'from app.graph import memory\nfrom app.reliability import collection_comparison, scope_context, research_scope_query, citations_in_answer, PLACEHOLDER\n')
    edit(p,'    decision, user_notes, internal = apply_policy(',
         '    if collection_comparison(q) or collection_comparison(decision.standalone_query):\n'
         '        decision.intent = "deep_research"\n'
         '        decision.standalone_query = research_scope_query(decision.standalone_query or q, scope_context(state))\n'
         '        deps.emit(rid, "policy", "supervisor", note="Collection-wide comparison requires research, not top-k retrieval")\n'
         '    decision, user_notes, internal = apply_policy(')
    edit(p,'    return {"research": meta, "draft_answer": res.answer,',
         '    return {"research_scope": {"question": scope_context(state) if collection_comparison(q) and scope_context(state) else q, "doc_ids": list(res.relevant_doc_ids)}, "research": meta, "draft_answer": res.answer,')
    out[p]=replace_fn(out[p],'_build_citations',CITATIONS)
    old='''        if has_evidence and not ID_RX.search(final) and "could not find" not in final.lower() and not research_mode:
            top = list(dict.fromkeys(h["chunk_id"] for h in evidence))[:3]
            final += "\\n\\nSources: " + ", ".join(f"[{c}]" for c in top)
            action = "sanitized"'''
    new='''        final = PLACEHOLDER.sub("", final)
        if has_evidence and not citations_in_answer(final) and not result.ok:
            final = "I could not produce a verifiably cited answer from the available evidence. Please retry or refine the question."
            action = "replaced"'''
    edit(p,old,new)
    p='app/graph/validators.py'
    edit(p,'import re\n','import re\nfrom app.reliability import PLACEHOLDER, citations_in_answer\n')
    edit(p,'    bad = invalid_ids(text, allowed_doc_ids, allowed_chunk_ids)\n',
         '    if PLACEHOLDER.search(text):\n'
         '        issues.append(_issue("placeholder_citation", "block", "Replace citation placeholders with actual evidence IDs"))\n'
         '    bad = invalid_ids(text, allowed_doc_ids, allowed_chunk_ids)\n')
    edit(p,'    if has_evidence and not ID_RX.search(text) and not refusal:\n',
         '    if has_evidence and not citations_in_answer(text) and not refusal:\n')
    p='scripts/run_acceptance.py'
    edit(p,"    if kind!='blocked': check('not blocked',not final.get('blocked'))\n",
         "    if kind!='blocked': check('not blocked',not final.get('blocked'))\n"
         "    check('no placeholder citations',not re.search(r'\\[(?:DOC_ID|CHUNK_ID|SOURCE_ID)\\]',answer,re.I))\n"
         "    if kind in {'longest','transactions'}:\n"
         "        check('bracketed evidence citation',bool(re.search(r'\\[[A-Z]{2,5}-(?:\\d{4}-)?\\d{3}(?:#\\d+)?\\]',answer)))\n"
         "    if kind in {'restricted','benign','abstain'} and re.search(r'could not find|couldn.t find|no relevant',lower):\n"
         "        check('no unrelated sources on abstention',not docs)\n")
    test_path='tests/test_graph.py'
    if (root/test_path).exists():
        text=(root/test_path).read_text()
        old='assert "INC-9999-999" not in res["final_answer"] and "Sources: [INC-2026-007#3]" in res["final_answer"]'
        new='assert "INC-9999-999" not in res["final_answer"] and "verifiably cited answer" in res["final_answer"]'
        if old in text:
            text=text.replace(old,new,1)
            text=text.replace('assert res["validation"]["action"] == "sanitized" and res["validation"]["ok"] is False and res["attempts"] == 2',
                              'assert res["validation"]["action"] == "replaced" and res["validation"]["ok"] is False and res["attempts"] == 2',1)
            out[test_path]=text
    for p,text in out.items():
        out[p]=text+'\n'+MARKER+'\n'
        compile(out[p],p,'exec')
    return out

CITATIONS='''def _build_citations(final: str, evidence: list[dict], evidence_ids: list[str], research_mode: bool) -> list[dict]:
    cited = citations_in_answer(final)
    if not cited:
        return []
    if research_mode:
        return [{"doc_id": d} for d in evidence_ids if d in cited]
    by_doc = {}
    for h in evidence:
        if h["doc_id"] not in cited and h["chunk_id"] not in cited:
            continue
        item = by_doc.setdefault(h["doc_id"], {"doc_id": h["doc_id"], "title": h["title"],
            "document_type": h["document_type"], "created_date": h["created_date"],
            "chunks": [], "top_score": h["score"]})
        item["chunks"].append(h["chunk_id"])
    return list(by_doc.values())
'''

if __name__=='__main__':
    out=build(Path('.'))
    for rel,text in out.items():
        p=Path(rel);p.with_suffix(p.suffix+'.reliability.bak').write_text(p.read_text());p.write_text(text)
        print('patched',rel)
    for name in ('README.md','config_guide.md'):
        p=Path(name);text=p.read_text() if p.exists() else '# Configuration guide\n'
        marker='## Acceptance reliability fixes'
        if marker not in text: p.write_text(text+'\n\n'+marker+'\nSee docs/reliability_fixes.md. No new settings.\n')
    print('Patch applied.' if out else 'Already patched.')

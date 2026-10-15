"""Python-based search plans (RLM step 2).

The planner LLM writes a tiny Python program over four whitelisted primitives. We NEVER exec it:
the code is parsed with `ast`, checked statement by statement (only `name = primitive(literal args)`),
and converted into a validated Plan object that our own executor runs.

    docs = select(document_types=["incident"], date_from="2025-10-16", keywords=["payment"])
    groups = batches(docs, size=3)
    findings = map_analyze(groups, question="What failed and why?")
    answer = reduce_all(findings, question="Which root causes recur?")

If the LLM output is invalid twice, a deterministic fallback plan is used (graceful degradation).
"""
import ast
import re
from datetime import date, timedelta
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.rlm.jsonutil import extract_code

DOC_TYPES = {"incident", "runbook", "architecture", "product_spec", "meeting_notes", "policy"}
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ALLOWED_KW = {
    "select": {"document_types", "department", "date_from", "date_to", "keywords", "match_in"},
    "batches": {"size"},
    "map_analyze": {"question"},
    "reduce_all": {"question"},
}
_ORDER = ["select", "batches", "map_analyze", "reduce_all"]


class PlanError(ValueError):
    pass


class SelectSpec(BaseModel):
    document_types: Optional[list[str]] = None
    department: Optional[str] = Field(default=None, pattern=r"^[A-Za-z0-9 _\-]{1,50}$")
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    keywords: list[str] = Field(default_factory=list, max_length=8)
    match_in: Literal["title", "any"] = "title"

    @field_validator("document_types")
    @classmethod
    def _types(cls, v):
        if v is not None and not set(v) <= DOC_TYPES:
            raise ValueError(f"unknown document types: {sorted(set(v) - DOC_TYPES)}")
        return v

    @field_validator("date_from", "date_to")
    @classmethod
    def _dates(cls, v):
        if v is not None:
            if not _ISO.match(v):
                raise ValueError("dates must be YYYY-MM-DD")
            date.fromisoformat(v)
        return v

    @field_validator("keywords")
    @classmethod
    def _kws(cls, v):
        if any((not isinstance(k, str)) or not 2 <= len(k) <= 40 for k in v):
            raise ValueError("keywords must be strings of 2 to 40 chars")
        return v


class Plan(BaseModel):
    select: SelectSpec
    batch_size: int
    analyze_question: str
    reduce_question: str
    code: str
    source: Literal["llm", "fallback"] = "llm"


def _literal(node: ast.AST):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError) as exc:
        raise PlanError("arguments must be plain literals") from exc


def _call_parts(stmt: ast.stmt, expected: str, prev_var: Optional[str]) -> tuple[str, dict]:
    if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name)
            and isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Name)):
        raise PlanError("each statement must look like: name = primitive(...)")
    call = stmt.value
    if call.func.id != expected:
        raise PlanError(f"expected call to {expected}(), got {call.func.id}()")
    if expected == "select":
        if call.args:
            raise PlanError("select() takes keyword arguments only")
    else:
        if len(call.args) != 1 or not isinstance(call.args[0], ast.Name) or call.args[0].id != prev_var:
            raise PlanError(f"{expected}() must take the previous variable '{prev_var}' as its only positional argument")
    kwargs = {}
    for kw in call.keywords:
        if kw.arg not in _ALLOWED_KW[expected]:
            raise PlanError(f"{expected}() does not accept '{kw.arg}'")
        kwargs[kw.arg] = _literal(kw.value)
    return stmt.targets[0].id, kwargs


def parse_plan(code: str, max_batch_size: int = 8) -> Plan:
    code = extract_code(code)
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise PlanError(f"syntax error: {exc.msg}") from exc
    if len(tree.body) != len(_ORDER):
        raise PlanError(f"plan must have exactly {len(_ORDER)} statements: {', '.join(_ORDER)}")
    parsed, prev = {}, None
    for stmt, name in zip(tree.body, _ORDER):
        var, kwargs = _call_parts(stmt, name, prev)
        parsed[name], prev = kwargs, var
    size = parsed["batches"].get("size", 3)
    if not isinstance(size, int) or not 1 <= size <= max_batch_size:
        raise PlanError(f"batch size must be an integer between 1 and {max_batch_size}")
    questions = []
    for fn in ("map_analyze", "reduce_all"):
        q = parsed[fn].get("question")
        if not isinstance(q, str) or not 3 <= len(q) <= 300:
            raise PlanError(f"{fn}() needs a question string of 3 to 300 chars")
        questions.append(q)
    try:
        spec = SelectSpec(**parsed["select"])
    except ValidationError as exc:
        raise PlanError(exc.errors()[0]["msg"]) from exc
    return Plan(select=spec, batch_size=size, analyze_question=questions[0], reduce_question=questions[1], code=code)


_STOP = {"summarize", "summarise", "summary", "identify", "related", "during", "last", "year", "report",
         "reports", "that", "with", "from", "all", "and", "the", "for", "recurring", "root", "cause", "causes",
         "what", "which", "show", "list", "over", "past", "months", "month", "about", "were", "have", "find"}


def default_plan(question: str, today: date, batch_size: int = 3) -> Plan:
    """Deterministic fallback: heuristics for time window, document type and topic keywords."""
    q = question.lower()
    date_from = None
    if re.search(r"(last|past|previous) (12 months|year)", q):
        date_from = (today - timedelta(days=365)).isoformat()
    elif m := re.search(r"(last|past) (\d{1,2}) months", q):
        date_from = (today - timedelta(days=30 * int(m.group(2)))).isoformat()
    types = None
    if re.search(r"incident|outage|failure|postmortem|root cause", q):
        types = ["incident"]
    elif "runbook" in q:
        types = ["runbook"]
    words = []
    for w_ in re.findall(r"[a-z][a-z\-]{3,}", q):
        w_ = w_[:-1] if w_.endswith("s") and not w_.endswith("ss") else w_
        if w_ not in _STOP and w_ not in words:
            words.append(w_)
    code = (f'docs = select(document_types={types!r}, date_from={date_from!r}, keywords={words[:3]!r})\n'
            f'groups = batches(docs, size={batch_size})\n'
            f'findings = map_analyze(groups, question="Is this document relevant to the request, and if so what is the root cause, affected service and key facts?")\n'
            f'answer = reduce_all(findings, question={question[:280]!r})')
    plan = parse_plan(code)
    plan.source = "fallback"
    return plan

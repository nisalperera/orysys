"""Supervisor decision: schema, heuristic fallback and server side policy application."""
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.auth.models import Role
from app.graph.policy import route_allowed
from app.rlm.guard import reconcile_select

DOC_TYPES = {"incident", "runbook", "architecture", "product_spec", "meeting_notes", "policy"}
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class SupervisorDecision(BaseModel):
    intent: Literal["chitchat", "knowledge_qa", "deep_research"] = "knowledge_qa"
    standalone_query: str = Field(default="", max_length=600)
    document_types: list[str] = Field(default_factory=list)
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    department: Optional[str] = None
    reason: str = Field(default="", max_length=300)

    @field_validator("document_types", mode="before")
    @classmethod
    def _types(cls, v):
        return [t for t in (v or []) if isinstance(t, str) and t in DOC_TYPES]

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def _dates(cls, v):
        return v if isinstance(v, str) and _ISO.match(v) else None

    @field_validator("department", mode="before")
    @classmethod
    def _dept(cls, v):
        return v if isinstance(v, str) and re.match(r"^[A-Za-z0-9 _\-]{1,50}$", v) else None


_GREETING = re.compile(r"^\s*(hi|hello|hey|thanks|thank you|good (morning|afternoon|evening)|who are you|what can you do)\b", re.I)
_RESEARCH = re.compile(r"(summari[sz]e all|all (the )?(incidents|outages|reports)|recurring|across (all|the)|trend|over the (last|past)|"
                       r"last (year|\d+ months)|compare .* (incidents|outages)|root causes)", re.I)


def heuristic_decision(question: str) -> SupervisorDecision:
    """Deterministic fallback when the supervisor LLM is unavailable or returns invalid output."""
    if _GREETING.search(question) and len(question) < 80:
        intent = "chitchat"
    elif _RESEARCH.search(question):
        intent = "deep_research"
    else:
        intent = "knowledge_qa"
    return SupervisorDecision(intent=intent, standalone_query=question, reason="heuristic fallback")


def apply_policy(decision: SupervisorDecision, role: Role, question: str,
                 known_departments: set) -> tuple[SupervisorDecision, list[str], list[str]]:
    """Enforce what the LLM cannot be trusted with: role limits and over-narrow filters.

    Returns (decision, user_notes, internal_notes). user_notes are appended to the answer, internal notes only
    go to the activity panel."""
    notes: list[str] = []
    d = decision.model_copy(deep=True)
    if len(d.standalone_query.strip()) < 2:  # empty or useless rewrite: fall back to the user's own words
        d.standalone_query = question
    if not route_allowed(role, d.intent):
        notes.append("Deep research across many documents is available to Analyst and Administrator roles. "
                     "A standard search was used instead.")
        d.intent = "knowledge_qa"
    args, dept_notes = reconcile_select({"department": d.department}, question, known_departments)
    d.department = args["department"]
    return d, notes, dept_notes

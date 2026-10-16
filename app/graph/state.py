"""Graph state. `messages` accumulates across turns (reducer: list concatenation), every other key is
overwritten by the node that returns it. Per-turn keys are reset in guard_input at the start of each turn."""
import operator
from typing import Annotated, TypedDict


class ChatState(TypedDict, total=False):
    # identity (server set, never model controlled)
    request_id: str
    user_id: str
    question: str
    # memory (persisted by the checkpointer per thread)
    messages: Annotated[list[dict], operator.add]
    memory_summary: str
    summarized_upto: int
    profile: dict
    episodes: list[dict]
    # per-turn
    route: dict
    policy_notes: list[str]
    retrieved: list[dict]
    retrieval_meta: dict
    research: dict
    evidence_ids: list[str]
    analysis_text: str
    draft_answer: str
    attempts: int
    validation: dict
    final_answer: str
    citations: list[dict]
    blocked_reason: str
    node_errors: list[str]

"""Data models and limits for the Recursive Language Model (RLM) engine."""
from dataclasses import dataclass
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


class DocRef(BaseModel):
    doc_id: str
    title: str
    document_type: str
    department: str
    access_level: str
    created_date: str


class DocFinding(BaseModel):
    doc_id: str
    relevant: bool = True
    root_cause: str = ""
    service: str = ""
    summary: str = ""
    evidence: list[str] = Field(default_factory=list)  # chunk ids, validated against retrieved chunks


class BatchResult(BaseModel):
    batch_id: str
    depth: int
    doc_ids: list[str]
    findings: list[DocFinding] = Field(default_factory=list)
    error: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class RLMResult(BaseModel):
    answer: str
    degraded: bool = False
    degraded_reasons: list[str] = Field(default_factory=list)
    plan_source: Literal["llm", "fallback"]
    plan_code: str
    docs_considered: int
    docs_truncated: bool = False
    batches: int
    max_depth_reached: int
    failed_batches: list[str] = Field(default_factory=list)
    relevant_doc_ids: list[str] = Field(default_factory=list)
    analysis: dict = Field(default_factory=dict)
    unverified_citations: list[str] = Field(default_factory=list)
    neutralized_snippets: int = 0


@dataclass
class RLMConfig:
    max_docs: int = 40
    default_batch_size: int = 3
    max_batch_size: int = 8
    max_depth: int = 2               # recursion cap for splitting oversized batches
    concurrency: int = 3             # parallel LLM calls (mind provider rate limits)
    context_char_budget: int = 6000  # max evidence characters per sub-agent call
    fan_in: int = 10                  # findings per reduce call (hierarchical reduce above this)
    max_reduce_rounds: int = 3
    llm_timeout_sec: float = 60.0
    llm_retries: int = 1
    retry_backoff_sec: float = 1.0
    today: Optional[date] = None     # injectable for tests

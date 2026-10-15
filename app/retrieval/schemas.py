"""Validated request/response models for knowledge search (also the knowledge_search tool schema in T4).

T3 change: `doc_ids` lets the RLM retrieve targeted sections of specific documents.
"""
import re
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

DocType = Literal["incident", "runbook", "architecture", "product_spec", "meeting_notes", "policy"]
_SAFE = r"^[A-Za-z0-9 _\-]{1,50}$"
_DOC_ID = re.compile(r"^[A-Za-z0-9_\-]{1,40}$")


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=6, ge=1, le=20)
    document_types: Optional[list[DocType]] = None
    department: Optional[str] = Field(default=None, pattern=_SAFE)
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    alpha: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    doc_ids: Optional[list[str]] = Field(default=None, max_length=50)

    @field_validator("query")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("doc_ids")
    @classmethod
    def _ids(cls, v):
        if v is not None:
            for i in v:
                if not _DOC_ID.match(i):
                    raise ValueError(f"invalid doc id: {i!r}")
        return v

    @model_validator(mode="after")
    def _dates(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be on or before date_to")
        return self


class Hit(BaseModel):
    chunk_id: str
    doc_id: str
    title: str
    section: str
    document_type: str
    department: str
    access_level: str
    created_date: str
    score: float
    text: str


class RetrievalResult(BaseModel):
    hits: list[Hit]
    namespaces_searched: list[str]
    failed_namespaces: list[str] = []
    degraded: bool = False
    degraded_reasons: list[str] = []
    alpha: float
    applied_filter: dict
    no_relevant_results: bool = False
    min_score: float = 0.0
    dropped_below_min_score: int = 0
    dropped_by_doc_cap: int = 0
    embed_ms: int = 0
    query_ms: int = 0
    latency_ms: int = 0

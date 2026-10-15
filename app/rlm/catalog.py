"""Document catalog: the RLM's 'explore the collection' surface.

The planner LLM only ever sees `stats()` (counts, date range), never document content.
Selection runs in plain Python over metadata, so thousands of documents never enter an LLM context.
Visibility is enforced here by the user's access tiers, and again by the retriever filter.
POC trade-off: the catalog is built from local files. In production it would be a metadata table.
"""
from collections import Counter
from typing import Iterable, Optional

from app.auth.models import User
from app.rlm.models import DocRef


class Catalog:
    def __init__(self, docs: Iterable):
        self._docs = {d.doc_id: d for d in docs}

    @classmethod
    def from_dir(cls, docs_dir: str) -> "Catalog":
        from app.retrieval.loader import load_all
        return cls(load_all(docs_dir))

    def _visible(self, user: User):
        return [d for d in self._docs.values() if d.access_level in user.access_levels]

    def stats(self, user: User) -> dict:
        vis = self._visible(user)
        dates = sorted(d.created_date for d in vis)
        return {
            "total_documents": len(vis),
            "date_range": [dates[0], dates[-1]] if dates else None,
            "by_document_type": dict(Counter(d.document_type for d in vis)),
            "by_department": dict(Counter(d.department for d in vis)),
        }

    def select(self, user: User, document_types: Optional[list[str]] = None, department: Optional[str] = None,
               date_from: Optional[str] = None, date_to: Optional[str] = None,
               keywords: Optional[list[str]] = None, match_in: str = "title") -> list[DocRef]:
        kws = [k.lower() for k in (keywords or []) if k]
        out = []
        for d in self._visible(user):
            if document_types and d.document_type not in document_types:
                continue
            if department and d.department != department:
                continue
            if date_from and d.created_date < date_from:
                continue
            if date_to and d.created_date > date_to:
                continue
            if kws:
                hay = d.title.lower() if match_in == "title" else f"{d.title}\n{d.body}".lower()
                if not any(k in hay for k in kws):
                    continue
            out.append(DocRef(doc_id=d.doc_id, title=d.title, document_type=d.document_type,
                              department=d.department, access_level=d.access_level, created_date=d.created_date))
        return sorted(out, key=lambda r: (r.created_date, r.doc_id))

    def body(self, doc_id: str) -> str:
        return self._docs[doc_id].body

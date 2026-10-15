"""Pinecone metadata filter builder. The access_level clause always comes from the user's role."""
from datetime import date, datetime, time, timezone

from app.auth.models import User
from app.retrieval.schemas import SearchRequest


def _ts(d: date, end_of_day: bool) -> int:
    t = time(23, 59, 59) if end_of_day else time(0, 0, 0)
    return int(datetime.combine(d, t, tzinfo=timezone.utc).timestamp())


def build_filter(user: User, req: SearchRequest) -> dict:
    clauses: list[dict] = [{"access_level": {"$in": list(user.access_levels)}}]
    if req.department:
        clauses.append({"department": {"$eq": req.department}})
    if req.date_from:
        clauses.append({"created_ts": {"$gte": _ts(req.date_from, False)}})
    if req.date_to:
        clauses.append({"created_ts": {"$lte": _ts(req.date_to, True)}})
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def namespaces_for(req: SearchRequest, all_namespaces: tuple[str, ...]) -> list[str]:
    if not req.document_types:
        return list(all_namespaces)
    return [n for n in all_namespaces if n in set(req.document_types)]

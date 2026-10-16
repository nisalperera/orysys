"""Server side routing policy. The LLM proposes an intent, this module decides what the role may actually run.
T4 generalises this into the tool registry (per tool allowed_roles)."""
from app.auth.models import Role

ROUTE_MIN_ROLE = {"chitchat": Role.VIEWER, "knowledge_qa": Role.VIEWER, "deep_research": Role.ANALYST}
_RANK = {Role.VIEWER: 0, Role.ANALYST: 1, Role.ADMIN: 2}


def route_allowed(role: Role, intent: str) -> bool:
    return _RANK[role] >= _RANK[ROUTE_MIN_ROLE.get(intent, Role.ADMIN)]

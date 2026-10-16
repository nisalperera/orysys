"""Option A authentication: hardcoded users, API key per user. T4 adds the full RBAC tool permissions.

Keys are compared in constant time. Override the demo keys with API_TOKENS='{"key": "viewer1", ...}' in .env.
"""
import hmac
import json
import os
from typing import Optional

from app.auth.models import USERS, User

DEFAULT_TOKENS = {"dev-viewer-key": "viewer1", "dev-analyst-key": "analyst1", "dev-admin-key": "admin1"}


def _tokens() -> dict[str, str]:
    raw = os.getenv("API_TOKENS")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items()}
        except json.JSONDecodeError:
            pass
    return DEFAULT_TOKENS


def authenticate_token(token: str) -> Optional[User]:
    found = None
    for key, user_id in _tokens().items():  # no early exit: constant work per attempt
        if hmac.compare_digest(key.encode(), (token or "").encode()):
            found = user_id
    return USERS.get(found) if found else None

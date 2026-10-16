"""Demo API-key authentication with validated, fail-closed overrides.

API_TOKENS absent: documented demo keys.
API_TOKENS set: only a valid explicit mapping is accepted.
An empty JSON mapping intentionally disables all API-key access.
"""
import hmac
import json
import logging
import os
from typing import Optional

from app.auth.models import USERS, User

log = logging.getLogger("auth")
DEFAULT_TOKENS = {
    "dev-viewer-key": "viewer1",
    "dev-analyst-key": "analyst1",
    "dev-admin-key": "admin1",
}
CONFIG_ERROR = "API_TOKENS must be a JSON object mapping non-empty string keys to known user IDs."


def _tokens() -> dict[str, str]:
    raw = os.getenv("API_TOKENS")
    if raw is None:
        return dict(DEFAULT_TOKENS)
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        raise ValueError(CONFIG_ERROR) from None
    if not isinstance(parsed, dict):
        raise ValueError(CONFIG_ERROR)
    for key, user_id in parsed.items():
        if (
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(user_id, str)
            or user_id not in USERS
        ):
            raise ValueError(CONFIG_ERROR)
    return dict(parsed)


def validate_token_config() -> None:
    """Call during startup to reject malformed explicit authentication config."""
    _tokens()


def authenticate_token(token: str) -> Optional[User]:
    try:
        configured = _tokens()
    except ValueError:
        # Environment changes after startup must never re-enable demo keys.
        log.error("Invalid API_TOKENS configuration; authentication denied")
        return None
    found = None
    for key, user_id in configured.items():
        if hmac.compare_digest(key.encode(), (token or "").encode()):
            found = user_id
    return USERS.get(found) if found else None

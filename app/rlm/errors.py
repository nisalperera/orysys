"""Classify LLM call failures so the RLM does not retry errors that can never succeed."""
import re

PERMANENT_HTTP = {400, 401, 403, 404}  # wrong model id, bad key, forbidden, not found


def http_status(exc: BaseException):
    code = getattr(exc, "status_code", None)
    if code is None:
        m = re.search(r"Error code: (\d{3})", str(exc))
        code = int(m.group(1)) if m else None
    return code


def is_permanent(exc: BaseException) -> bool:
    return http_status(exc) in PERMANENT_HTTP

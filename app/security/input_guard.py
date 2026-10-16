"""Input guard for user messages (first layer of prompt injection defence).

Heuristics catch the common attack classes named in the brief: instruction override, data exfiltration and tool
abuse (plus role escalation). It is deliberately conservative to avoid blocking normal banking questions such as
"show me the password reset policy". T5 adds an LLM based classifier on top and a full test corpus.
Blocked messages are never written to conversation memory (prevents memory poisoning).
"""
import re
from dataclasses import dataclass

MAX_LEN = 2000
_I = re.IGNORECASE
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

_RULES = [
    ("instruction_override", re.compile(
        r"(ignore|disregard|forget|override)\s+(all\s+|any\s+|the\s+|your\s+)?(previous|prior|above|earlier|system)\s+"
        r"(instructions|rules|prompts?|guidelines)", _I)),
    ("prompt_exfiltration", re.compile(
        r"(reveal|show|print|repeat|output|display|leak)\s+(me\s+)?(your|the)\s+(system|hidden|initial|secret)\s+"
        r"(prompt|instructions|message)", _I)),
    ("secret_exfiltration", re.compile(
        r"(reveal|show|print|dump|send|leak|exfiltrate|list)\s+(me\s+)?(all|every|your|the\s+system'?s?|stored|admin|internal)\s+"
        r"(api[\s_-]?keys?|secrets?|passwords?|credentials|tokens)", _I)),
    ("role_escalation", re.compile(
        r"((you are now|pretend (to be|you are)|from now on,? you are)\s+.{0,30}(admin(istrator)?|root|developer|unrestricted|dan)\b"
        r"|(enable|switch to|activate)\s+(admin|developer|god|debug)\s+mode)", _I)),
    ("tool_abuse", re.compile(
        r"((call|invoke|run|execute|use)\s+(the\s+)?(admin|delete|shell|root)\s+(tool|command|function))"
        r"|\b(delete_index|drop\s+table|rm\s+-rf)\b", _I)),
]


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    text: str
    category: str = ""
    reason: str = ""


def check_user_input(text: str | None) -> GuardResult:
    clean = _CTRL.sub("", (text or "")).strip()
    if len(clean) < 2:
        return GuardResult(False, clean, "empty", "message is empty or too short")
    if len(clean) > MAX_LEN:
        return GuardResult(False, clean[:200], "too_long", f"message longer than {MAX_LEN} characters")
    for category, rx in _RULES:
        if rx.search(clean):
            return GuardResult(False, clean, category, f"matched {category} pattern")
    return GuardResult(True, clean)

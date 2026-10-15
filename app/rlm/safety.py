"""Minimal retrieved-content sanitiser used by the RLM. T5 replaces/extends it with the full guardrail layer."""
import re

_INJ = re.compile(
    r"(ignore\s+(all\s+)?(the\s+)?(previous|prior|above)\s+(instructions|prompts)"
    r"|disregard\s.{0,40}instructions"
    r"|you\s+are\s+now\s+(in\s+)?\w+\s+mode"
    r"|reveal\s.{0,40}(system\s+prompt|api\s+key|secret|password)"
    r"|(call|invoke|run)\s+the\s.{0,30}\btool\b"
    r"|delete_index)", re.I)
REMOVED = "[removed: suspected instruction found in document]"


def neutralize_injection(text: str) -> tuple[str, int]:
    """Replace any line that looks like an instruction aimed at the model. Returns (clean_text, lines_removed)."""
    out, removed = [], 0
    for line in text.splitlines():
        if _INJ.search(line):
            out.append(REMOVED)
            removed += 1
        else:
            out.append(line)
    return "\n".join(out), removed

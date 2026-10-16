"""Output guardrails (pure functions, no LLM): hallucinated citations, empty answers, secret leakage,
missing citations and ungrounded numbers. Every check is explainable, which matters for the demo."""
import re
from app.reliability import PLACEHOLDER, citations_in_answer
from dataclasses import dataclass, field

ID_RX = re.compile(r"\b[A-Z]{2,5}-(?:\d{4}-)?\d{3}(?:#\d+)?\b")
_NUM_RX = re.compile(r"\b\d[\d,]*\.?\d*\b")
_SECRET_RX = re.compile(r"(sk-[A-Za-z0-9_\-]{16,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|pcsk_[A-Za-z0-9_]{10,}|"
                        r"lsv2_[A-Za-z0-9_]{10,}|api[_ ]?key\s*[:=]\s*\S{8,})", re.I)
_REFUSAL_RX = re.compile(r"(could not find|couldn't find|no (accessible|relevant)|do not have (enough )?information|"
                         r"don't have (enough )?information|unable to find|not able to find)", re.I)


@dataclass
class ValidationResult:
    ok: bool
    issues: list[dict] = field(default_factory=list)

    @property
    def blocking(self) -> list[dict]:
        return [i for i in self.issues if i["severity"] == "block"]


def _issue(code: str, severity: str, message: str) -> dict:
    return {"code": code, "severity": severity, "message": message}


def _base(i: str) -> str:
    return i.split("#")[0]


def _allowed_mention(
    answer: str,
    match: re.Match,
    mentioned_ids: set[str],
) -> bool:
    """Allow user-provided IDs in prose, never inside source brackets."""
    if match.group(0) not in mentioned_ids:
        return False

    bracket_spans = re.finditer(r"\[[^\]\n]*\]", answer)
    return not any(
        bracket.start() <= match.start() < bracket.end()
        for bracket in bracket_spans
    )


def invalid_ids(
    answer: str,
    allowed_doc_ids: set[str],
    allowed_chunk_ids: set[str],
    mentioned_ids: set[str] | None = None,
) -> list[str]:
    mentioned_ids = mentioned_ids or set()
    bad = []

    for match in ID_RX.finditer(answer):
        identifier = match.group(0)

        supported = (
            identifier in allowed_chunk_ids
            if "#" in identifier
            else identifier in allowed_doc_ids
        )

        if supported or _allowed_mention(answer, match, mentioned_ids):
            continue

        if identifier not in bad:
            bad.append(identifier)

    return bad


def ungrounded_numbers(answer: str, evidence_text: str) -> list[str]:
    ev = {t.rstrip(".,").replace(",", "") for t in _NUM_RX.findall(evidence_text)}
    out = []
    for tok in _NUM_RX.findall(ID_RX.sub(" ", answer)):
        digits = tok.rstrip(".,").replace(",", "")
        if len(digits.replace(".", "")) < 3 or re.fullmatch(r"(19|20)\d{2}", digits):
            continue
        if digits not in ev and tok not in out:
            out.append(tok)
    return out


def validate_answer(
    answer: str,
    allowed_doc_ids: set[str],
    allowed_chunk_ids: set[str],
    evidence_text: str,
    has_evidence: bool,
    mentioned_ids: set[str] | None = None,
) -> ValidationResult:
    issues: list[dict] = []
    text = (answer or "").strip()
    if len(text) < 3:
        issues.append(_issue("empty_answer", "block", "the answer is empty"))
        return ValidationResult(False, issues)
    if _SECRET_RX.search(text):
        issues.append(_issue("secret_leak", "block", "the answer contains something that looks like a secret"))
    if PLACEHOLDER.search(text):
        issues.append(_issue("placeholder_citation", "block", "Replace citation placeholders with actual evidence IDs"))
    bad = invalid_ids(text, allowed_doc_ids, allowed_chunk_ids, mentioned_ids=mentioned_ids)
    if bad:
        issues.append(_issue("unknown_citation", "block", f"cited ids not in the retrieved evidence: {bad}"))
    refusal = bool(_REFUSAL_RX.search(text))
    if has_evidence and not citations_in_answer(text) and not refusal:
        issues.append(_issue("missing_citation", "block", "the answer cites no source"))
    nums = ungrounded_numbers(text, evidence_text)
    if nums:
        issues.append(_issue("ungrounded_number", "warn", f"numbers not found in the evidence: {nums[:6]}"))
    return ValidationResult(not any(i["severity"] == "block" for i in issues), issues)


def strip_invalid_citations(
    text: str,
    allowed_doc_ids: set[str],
    allowed_chunk_ids: set[str],
    mentioned_ids: set[str] | None = None,
) -> str:
    mentioned_ids = mentioned_ids or set()

    bad = set(
        invalid_ids(
            text,
            allowed_doc_ids,
            allowed_chunk_ids,
            mentioned_ids=mentioned_ids,
        )
    )

    if not bad:
        return text

    def replace(match: re.Match) -> str:
        identifier = match.group(0)

        if identifier not in bad:
            return identifier

        if _allowed_mention(text, match, mentioned_ids):
            return identifier

        return ""

    out = ID_RX.sub(replace, text)
    out = re.sub(r"\[\s*,\s*", "[", out)
    out = re.sub(r"\s*,\s*\]", "]", out)
    out = re.sub(r",\s*,", ",", out)
    out = re.sub(r"\s*\[\s*\]", "", out)

    return re.sub(r"[ \t]{2,}", " ", out)


def build_feedback(issues: list[dict]) -> str:
    return "; ".join(i["message"] for i in issues if i["severity"] == "block")

# acceptance-reliability-v1

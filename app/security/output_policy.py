"""Fail-closed final output policy. RAG stage: generate/validate."""

from app.graph.validators import strip_invalid_citations, validate_answer
from app.reliability import PLACEHOLDER


SAFE_ANSWER = (
    "I could not produce a verifiably cited answer from the available evidence. "
    "Please retry or refine the question."
)

SECRET_ANSWER = (
    "I can't share that response because it may contain sensitive information. "
    "Please rephrase your question."
)


def finalize_output(
    draft,
    docs,
    chunks,
    evidence_text,
    has_evidence,
    mentioned_ids=None,
):
    mentioned_ids = mentioned_ids or set()

    original = validate_answer(
        draft,
        docs,
        chunks,
        evidence_text,
        has_evidence,
        mentioned_ids=mentioned_ids,
    )

    if any(issue["code"] == "secret_leak" for issue in original.issues):
        final, action = SECRET_ANSWER, "replaced"

    else:
        final = PLACEHOLDER.sub(
            "",
            strip_invalid_citations(
                draft,
                docs,
                chunks,
                mentioned_ids=mentioned_ids,
            ),
        ).strip()

        check = validate_answer(
            final,
            docs,
            chunks,
            evidence_text,
            has_evidence,
            mentioned_ids=mentioned_ids,
        )

        if not check.ok:
            final, action = SAFE_ANSWER, "replaced"
        else:
            action = "sanitized" if final != draft else "passed"

    if action == "replaced":
        check = validate_answer(final, set(), set(), "", False)
    else:
        check = validate_answer(
            final,
            docs,
            chunks,
            evidence_text,
            has_evidence,
            mentioned_ids=mentioned_ids,
        )

    return final, action, check

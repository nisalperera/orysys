from app.security.output_policy import finalize_output, SAFE_ANSWER, SECRET_ANSWER


def test_empty_output_is_replaced_even_without_evidence():
    final, action, check = finalize_output("", set(), set(), "", False)
    assert final == SAFE_ANSWER and action == "replaced" and check.ok


def test_user_supplied_unknown_source_does_not_authorize_citation():
    final, action, check = finalize_output(
        "Answer [INC-2099-999]", {"INC-2026-007"}, {"INC-2026-007#0"}, "Evidence", True
    )
    assert final == SAFE_ANSWER and action == "replaced" and check.ok


def test_mixed_invalid_and_valid_sources_are_sanitized_and_rechecked():
    final, action, check = finalize_output(
        "Answer [INC-2099-999] [INC-2026-007#0]",
        {"INC-2026-007"}, {"INC-2026-007#0"}, "Evidence", True,
    )
    assert "2099" not in final and "INC-2026-007#0" in final
    assert action == "sanitized" and check.ok


def test_secret_output_is_replaced():
    final, action, check = finalize_output("sk-" + "a" * 24, set(), set(), "", False)
    assert final == SECRET_ANSWER and action == "replaced" and check.ok


def test_user_provided_id_can_be_mentioned_in_refusal():
    text = (
        "I could not find INC-2030-777 "
        "in the documents available to you."
    )

    final, action, check = finalize_output(
        text,
        set(),
        set(),
        "",
        False,
        mentioned_ids={"INC-2030-777"},
    )

    assert final == text
    assert action == "passed"
    assert check.ok


def test_user_provided_id_cannot_be_used_as_unsupported_citation():
    final, action, check = finalize_output(
        "The incident was resolved [INC-2030-777].",
        {"INC-2026-007"},
        {"INC-2026-007#0"},
        "Retrieved evidence",
        True,
        mentioned_ids={"INC-2030-777"},
    )

    assert final == SAFE_ANSWER
    assert action == "replaced"
    assert check.ok


def test_prose_mention_survives_when_same_id_has_invalid_citation():
    text = (
        "You asked about INC-2030-777. "
        "Supported detail [INC-2026-007#0]. "
        "Unsupported source [INC-2030-777]."
    )

    final, action, check = finalize_output(
        text,
        {"INC-2026-007"},
        {"INC-2026-007#0"},
        "Retrieved evidence",
        True,
        mentioned_ids={"INC-2030-777"},
    )

    assert "You asked about INC-2030-777." in final
    assert "[INC-2030-777]" not in final
    assert "[INC-2026-007#0]" in final
    assert action == "sanitized"
    assert check.ok
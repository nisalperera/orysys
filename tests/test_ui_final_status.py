from ui.client import Turn


def final_event(**updates):
    data = {"answer": "Final answer", "blocked": False, "degraded": False}
    data.update(updates)
    return {"type": "final", "data": data}


def test_degraded_final_has_distinct_activity_status():
    turn = Turn()
    turn.accept(final_event(degraded=True))
    assert turn.label == "Complete — degraded"


def test_blocked_status_takes_precedence_over_degraded():
    turn = Turn()
    turn.accept(final_event(blocked=True, degraded=True))
    assert turn.label == "Blocked"


def test_ordinary_final_remains_complete():
    turn = Turn()
    turn.accept(final_event())
    assert turn.label == "Complete"


def test_final_validation_replaces_earlier_activity_snapshot():
    turn = Turn()
    turn.accept({"type": "validation", "data": {"ok": False, "action": "retry"}})
    turn.accept(final_event(validation={"ok": False, "final_ok": True, "action": "sanitized"}))
    assert turn.validation == {"ok": False, "final_ok": True, "action": "sanitized"}


def test_absent_final_validation_preserves_earlier_snapshot():
    turn = Turn()
    turn.accept({"type": "validation", "data": {"ok": True}})
    turn.accept(final_event())
    assert turn.validation == {"ok": True}

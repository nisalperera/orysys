"""Plan guard: stop the planner LLM from silently narrowing the search.

Observed failure: for "payment failures last year" the planner added department="payments". Two payment
incidents filed under the "cards" department (expired TLS certificate) were dropped, and the answer looked
complete while missing a recurring root cause. Recall errors like this are invisible in the final text.

Rule: a department filter is honoured only if the user's question actually names that department.
Everything else (type, dates, topic keywords) stays, and the batch analysers discard irrelevant documents.
"""


def reconcile_select(select_args: dict, question: str, known_departments: set[str]) -> tuple[dict, list[str]]:
    """Returns (possibly adjusted select kwargs, human readable notes). Pure function, input is not mutated."""
    args, notes = dict(select_args), []
    dept = args.get("department")
    if dept and dept.lower() not in question.lower():
        notes.append(f"dropped department filter '{dept}': the question does not name that department")
        args["department"] = None
    return args, notes

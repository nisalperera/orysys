"""Makes tracing problems non-fatal for retrieval (run once from the repo root, .bak backup, anchor checked first).

Observed: with agent addressing configured, LangSmith raised LangSmithUserError when the traced `hybrid_search` span was
created inside a LangGraph run (it inherited project 'default' and also had an address). The error escaped into the
retrieval node, which then told the user the document store was down. A monitoring misconfiguration must never take the
product down: on a LangSmith error the search now runs untraced.
"""
from pathlib import Path

OLD = '    return await run(req.query, req.model_dump(mode="json", exclude={"query"}, exclude_none=True), user.role.value)\n'
NEW = (
    '    try:\n'
    '        return await run(req.query, req.model_dump(mode="json", exclude={"query"}, exclude_none=True), user.role.value)\n'
    '    except Exception as exc:  # noqa: BLE001  tracing must never break retrieval\n'
    '        if not type(exc).__module__.startswith("langsmith"):\n'
    '            raise\n'
    '        log.warning("LangSmith tracing error, searching untraced: %s", exc)\n'
    '        return await asyncio.wait_for(deps.search(user, req), deps.search_timeout)\n'
)


def apply(path: Path = Path("app/graph/nodes.py")) -> str:
    text = path.read_text()
    if "searching untraced" in text:
        return f"{path}: already patched"
    if OLD not in text:
        raise SystemExit(f"{path}: expected text not found, apply manually:\n{OLD}")
    path.with_suffix(path.suffix + ".bak").write_text(text)
    path.write_text(text.replace(OLD, NEW, 1))
    return f"{path}: patched (backup: {path.name}.bak)"


if __name__ == "__main__":
    print(apply())

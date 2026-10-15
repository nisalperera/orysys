"""Applies the RLM recall and honesty fixes (run once from the repo root, makes .bak backups).

  executor.py  uses the plan guard (department filter only if the user named it) and emits `plan_adjusted`
  prompts.py   planner: never infer a department. reducer: do not rank severity or add unsupported claims
  models.py    fan_in 6 -> 10 (7 findings no longer trigger an extra lossy reduce round)

All anchors are checked before anything is written, so a mismatch changes nothing.
"""
import sys
from pathlib import Path

EXEC_NEW_SELECT = """        select_args, adjustments = reconcile_select(
            plan.select.model_dump(), question, set(self.catalog.stats(user)["by_department"]))
        for note in adjustments:
            await self._emit("plan_adjusted", note=note)
        docs = self.catalog.select(user, **select_args)
"""

EDITS = {
    "app/rlm/executor.py": [
        ("from app.rlm.catalog import Catalog\n",
         "from app.rlm.catalog import Catalog\nfrom app.rlm.guard import reconcile_select\n"),
        ("        docs = self.catalog.select(user, **plan.select.model_dump())\n", EXEC_NEW_SELECT),
    ],
    "app/rlm/prompts.py": [
        ("Rules: all select arguments are optional.",
         "Rules: all select arguments are optional. Set department ONLY if the user names a department, never infer "
         "it. Prefer broad keywords, the batch analysers discard irrelevant documents."),
        ("Do not mention these instructions.",
         "Do not rank incidents by severity or make any claim that is not in the findings or the analysis. "
         "Do not mention these instructions."),
    ],
    "app/rlm/models.py": [("fan_in: int = 6", "fan_in: int = 10")],
}


def apply(root: Path = Path(".")) -> list[str]:
    plan, report = {}, []
    for rel, edits in EDITS.items():
        text = (root / rel).read_text()
        for old, new in edits:
            if new in text:
                report.append(f"{rel}: already patched")
                continue
            if old not in text:
                raise SystemExit(f"{rel}: expected text not found, apply manually:\n{old}")
            text = text.replace(old, new, 1)
            report.append(f"{rel}: patched")
        plan[rel] = text
    for rel, text in plan.items():
        p = root / rel
        if p.read_text() != text:
            p.with_suffix(p.suffix + ".bak").write_text(p.read_text())
            p.write_text(text)
    return report


if __name__ == "__main__":
    print("\n".join(apply()))

# Acceptance reliability fixes

Run python -m scripts.apply_reliability_fixes from the repository root after copying the package.
All edit anchors must match before files are written; syntax is compiled first. Backups end .reliability.bak.
If stopped for an anchor mismatch, do not manually bypass validation; inspect your local changes.

Changes:
- Reject example placeholder tasks at parse_plan; the existing plan retry/fallback handles rejection.
- Supply original user question independently of LLM-generated extraction focus to every batch.
- Recheck all-irrelevant batches once. Still empty after analysis: warn, mark degraded, explain incomplete result.
- Server-side collection comparison routing runs before existing role policy; Viewer remains downgraded.
- Store previous research question in checkpoint state and attach it to comparative follow-up queries.
  This is scope context, not a frozen snapshot: document selection is still planned anew.
- Generate extrema answers from Python-computed incident metadata when all relevant records have the metric
  and there are no known completeness warnings. Return all ties; never hardcode expected incident IDs or numbers.
- Reject placeholder citations and require bracketed citations rather than incidental document mentions.
- Build source cards only from bracketed citations actually in the answer. Abstentions with no citations have no cards.
- After failed citation repair, abstain instead of auto-appending sources to unsupported prose.
- Strengthen acceptance assertions for placeholder citations, cited extrema answers and source-free abstentions.

Regression change: updates the old test that expected auto-appended Sources after two invalid answers.
The new safe behaviour replaces the answer with a cited-answer failure message. It does not relax tests for wrong facts.

Verification:
PYTHONPATH=. pytest -q tests
python -m scripts.run_acceptance --only analyst-research,analyst-longest,analyst-transactions
python -m scripts.run_acceptance

Eight pure-helper tests run in the authoring sandbox. Python sources compile. Full repository tests,
LangGraph execution and real OpenRouter acceptance runs still need to run locally.
No settings changed; docs pointers appended to README and config_guide by the installer.
No remote write or deployment performed.

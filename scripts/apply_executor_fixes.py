"""Applies two small fixes to app/rlm/executor.py (run once from the repo root, makes a .bak backup):

  1. do not retry permanent LLM errors (wrong model id, bad key): fail fast
  2. when EVERY batch failed, say the analysis could not be done, not "no relevant documents"

Each replacement is asserted, so the script stops loudly if your file differs from the expected text.
"""
import sys
from pathlib import Path

P = Path("app/rlm/executor.py")
text = P.read_text()
if "is_permanent" in text:
    print("already patched")
    sys.exit(0)

EDITS = [
    ("from app.rlm.catalog import Catalog\n",
     "from app.rlm.catalog import Catalog\nfrom app.rlm.errors import is_permanent\n"),
    ("""            except Exception as exc:  # noqa: BLE001
                last = exc
                if attempt < self.cfg.llm_retries:
""",
     """            except Exception as exc:  # noqa: BLE001
                last = exc
                if is_permanent(exc):
                    break  # wrong model id / bad key: retrying cannot succeed
                if attempt < self.cfg.llm_retries:
"""),
    ("""            msg = "No relevant documents were found for this request."
            if failed:
                msg += " Some batches failed, so the search may be incomplete."
""",
     """            if failed and all(b.error for b in batch_results):
                msg = ("The documents could not be analysed because the language model service failed. "
                       "Please try again.")
            else:
                msg = "No relevant documents were found for this request."
                if failed:
                    msg += " Some batches failed, so the search may be incomplete."
"""),
]
for old, new in EDITS:
    if old not in text:
        sys.exit(f"Expected text not found, apply manually:\n{old}")
    text = text.replace(old, new, 1)
P.with_suffix(".py.bak").write_text(P.read_text())
P.write_text(text)
print("patched app/rlm/executor.py (backup: executor.py.bak)")

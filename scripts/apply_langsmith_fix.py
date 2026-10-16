"""Makes .env values visible to LangSmith (run once from the repo root, makes a .bak backup).

pydantic-settings fills the Settings object from .env but does not export the values to os.environ. LangSmith and
LangChain read os.environ, so LANGSMITH_* in .env alone does not switch tracing on. This adds load_dotenv() to
app/config.py (variables already set in the shell keep priority).
"""
import sys
from pathlib import Path

ANCHOR = "from functools import lru_cache\n"
BLOCK = (
    "from functools import lru_cache\n"
    "\n"
    "from dotenv import load_dotenv\n"
    "\n"
    "# LangSmith and LangChain read os.environ, while pydantic-settings only fills the Settings object.\n"
    "load_dotenv()  # shell variables win over .env\n"
)


def apply(path: Path = Path("app/config.py")) -> str:
    text = path.read_text()
    if "load_dotenv()" in text:
        return f"{path}: already patched"
    if ANCHOR not in text:
        raise SystemExit(f"{path}: anchor line not found. Add these lines near the top by hand:\n{BLOCK}")
    path.with_suffix(path.suffix + ".bak").write_text(text)
    path.write_text(text.replace(ANCHOR, BLOCK, 1))
    return f"{path}: patched (backup: {path.name}.bak)"


if __name__ == "__main__":
    print(apply())
    sys.exit(0)

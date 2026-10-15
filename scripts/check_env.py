"""Diagnose .env problems without ever printing secret values.

python -m scripts.check_env [path]

Finds the lines python-dotenv cannot parse (reported by line number and key name only) and checks that the
LLM and retrieval settings needed by this project are present.
"""
import re
import sys
from pathlib import Path

NON_SECRET = {"BASE_URL", "LLM_MODEL", "EMBEDDING_MODEL", "EMBEDDING_BASE_URL", "PINECONE_INDEX", "EMBEDDING_DIM"}
REQUIRED = ["BASE_URL", "API_KEY", "LLM_MODEL", "PINECONE_API_KEY", "PINECONE_INDEX"]
_KEY = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_.\-]*)\s*=(.*)$")


def check_lines(text: str) -> tuple[list[tuple[int, str, str]], dict[str, str]]:
    issues, values = [], {}
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _KEY.match(raw)
        if not m:
            issues.append((n, "?", "not in KEY=VALUE form (a bare value, a stray fragment, or a missing '=')"))
            continue
        key, val = m.group(1), m.group(2).strip()
        values[key] = val
        if val[:1] in ("'", '"'):
            q = val[0]
            end = val.find(q, 1)
            if end < 0:
                issues.append((n, key, f"opening {q} quote is never closed"))
            elif val[end + 1:].strip() and not val[end + 1:].strip().startswith("#"):
                issues.append((n, key, "extra characters after the closing quote"))
        elif re.search(r"\s", val.split(" #")[0].strip()):
            issues.append((n, key, "value contains spaces but is not quoted, wrap it in double quotes"))
    return issues, values


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else ".env")
    if not path.exists():
        print(f"{path} not found")
        return 2
    issues, values = check_lines(path.read_text())
    bad = False
    for n, key, msg in issues:
        bad = True
        print(f"line {n} ({key}): {msg}")
    for key in REQUIRED:
        v = values.get(key, "").strip("'\"")
        if not v:
            bad = True
            print(f"missing or empty: {key}")
        elif key in NON_SECRET:
            print(f"ok: {key}={v}")
        else:
            print(f"ok: {key} is set ({len(v)} chars)")
    base, model = values.get("BASE_URL", ""), values.get("LLM_MODEL", "").strip("'\"")
    if "openrouter.ai" in base and ("AWQ" in model or model.count("/") != 1):
        bad = True
        print(f"LLM_MODEL '{model}' does not look like an OpenRouter slug (expected vendor/model, see openrouter.ai/models)")
    print("PROBLEMS FOUND" if bad else "all good")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

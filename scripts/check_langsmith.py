"""Self-test for LangSmith tracing (project addressing and agent addressing). Never prints the API key.

python -m scripts.check_langsmith

Agent addressing (LANGSMITH_AGENT_ID + LANGSMITH_AGENT_ENVIRONMENT) needs langsmith>=0.14.4, must not be combined with a
project variable, and traces appear under Agent > Tracing > Environment, not under Projects.
"""
import logging
import os
import re
import sys
import time

from dotenv import load_dotenv

load_dotenv()

AGENT_ENVS = {"local", "development", "staging", "production"}
AGENT_ID_RX = re.compile(r"^[a-z]([a-z0-9-]{0,61}[a-z0-9])?$")
MIN_AGENT_SDK = (0, 14, 4)
PROJECT_VARS = ("LANGSMITH_PROJECT", "LANGCHAIN_PROJECT", "LANGCHAIN_SESSION")


def parse_version(v: str) -> tuple:
    return tuple(int(p) for p in re.findall(r"\d+", v)[:3])


def diagnose(env, sdk_version: str | None = None) -> tuple[dict, list[str]]:
    tracing = (env.get("LANGSMITH_TRACING") or env.get("LANGCHAIN_TRACING_V2") or "").strip()
    key = env.get("LANGSMITH_API_KEY") or env.get("LANGCHAIN_API_KEY") or ""
    agent = (env.get("LANGSMITH_AGENT_ID") or "").strip()
    agent_env = (env.get("LANGSMITH_AGENT_ENVIRONMENT") or "").strip()
    project_vars = [v for v in PROJECT_VARS if env.get(v)]
    mode = "agent" if (agent or agent_env) else "project"
    info = {
        "mode": f"{mode} addressing",
        "tracing": tracing or "(not set)",
        "api_key": f"set ({len(key)} chars)" if key else "(not set)",
        "endpoint": env.get("LANGSMITH_ENDPOINT") or "default (api.smith.langchain.com)",
        "sdk": sdk_version or "(langsmith not installed)",
    }
    if mode == "agent":
        info.update(agent=agent or "(not set)", environment=agent_env or "(not set)")
    else:
        info["project"] = env.get("LANGSMITH_PROJECT") or env.get("LANGCHAIN_PROJECT") or "default"

    problems = []
    if tracing.lower() not in ("true", "1"):
        problems.append("tracing is not enabled: set LANGSMITH_TRACING=true in .env")
    if not key:
        problems.append("no API key: set LANGSMITH_API_KEY in .env")
    if mode == "agent":
        if not (agent and agent_env):
            problems.append("set BOTH LANGSMITH_AGENT_ID and LANGSMITH_AGENT_ENVIRONMENT, with only one the SDK sends nothing")
        if agent and not AGENT_ID_RX.match(agent):
            problems.append("LANGSMITH_AGENT_ID must be the agent identifier: 1 to 63 lowercase letters, digits or hyphens")
        if agent_env and agent_env not in AGENT_ENVS:
            problems.append(f"LANGSMITH_AGENT_ENVIRONMENT must be one of {sorted(AGENT_ENVS)} (lowercase)")
        if project_vars:
            problems.append(f"{', '.join(project_vars)} is set together with the agent variables: the SDK refuses to pick "
                            "one destination and sends nothing. Remove the project variable from .env")
        if sdk_version and parse_version(sdk_version) < MIN_AGENT_SDK:
            problems.append(f"langsmith {sdk_version} is too old for agent addressing, run: pip install -U 'langsmith>=0.14.4'")
    return info, problems


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="SDK warning: %(message)s")
    try:
        from importlib.metadata import version
        sdk = version("langsmith")
    except Exception:  # noqa: BLE001
        sdk = None
    info, problems = diagnose(os.environ, sdk)
    for k, v in info.items():
        print(f"{k:11}: {v}")
    if problems:
        print("\n".join(f"PROBLEM: {p}" for p in problems))
        return 1

    from langsmith import Client, traceable

    @traceable(name="langsmith_selftest")
    def ping(x: int) -> int:
        return x * 2

    ping(21)
    client = Client()
    try:
        client.flush()
    except Exception:  # noqa: BLE001  older SDKs have no flush, the wait below covers it
        pass
    time.sleep(5)

    if info["mode"].startswith("agent"):
        print(f"Test trace sent. Open LangSmith, select agent '{info['agent']}' in the top bar, go to Tracing and set the "
              f"environment to '{info['environment']}'. Agent traces are NOT listed under Projects.")
        print("If it is missing: check that the key belongs to the agent-based workspace of this endpoint's region, and "
              "read any 'SDK warning' lines above.")
        return 0
    try:
        names = [r.name for r in client.list_runs(project_name=info["project"], limit=5)]
    except Exception as exc:  # noqa: BLE001
        print(f"PROBLEM: could not read project '{info['project']}': {type(exc).__name__}: {str(exc)[:200]}")
        return 1
    print("latest runs in project:", names)
    ok = "langsmith_selftest" in names
    print("OK: trace arrived." if ok else "PROBLEM: the test trace is not visible yet, wait and run again, then check key, region, project.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

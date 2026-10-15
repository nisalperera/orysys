from scripts.check_langsmith import diagnose, parse_version

BASE = {"LANGSMITH_TRACING": "true", "LANGSMITH_API_KEY": "lsv2_secret_value_123",
        "LANGSMITH_ENDPOINT": "https://apac.api.smith.langchain.com",
        "LANGSMITH_AGENT_ID": "orysys", "LANGSMITH_AGENT_ENVIRONMENT": "local"}


def test_valid_agent_config_has_no_problems_and_hides_the_key():
    info, problems = diagnose(BASE, "0.14.4")
    assert problems == [] and info["mode"] == "agent addressing" and "secret" not in str(info)
    assert info["agent"] == "orysys" and info["environment"] == "local"


def test_agent_and_project_together_is_flagged():
    for var in ("LANGSMITH_PROJECT", "LANGCHAIN_PROJECT", "LANGCHAIN_SESSION"):
        _, problems = diagnose({**BASE, var: "lmb-ai-assistant"}, "0.14.4")
        assert any(var in p and "Remove" in p for p in problems)


def test_agent_config_errors():
    only_one = {k: v for k, v in BASE.items() if k != "LANGSMITH_AGENT_ENVIRONMENT"}
    assert any("BOTH" in p for p in diagnose(only_one, "0.14.4")[1])
    assert any("one of" in p for p in diagnose({**BASE, "LANGSMITH_AGENT_ENVIRONMENT": "prod"}, "0.14.4")[1])
    assert any("lowercase" in p for p in diagnose({**BASE, "LANGSMITH_AGENT_ID": "My Agent"}, "0.14.4")[1])
    assert any("too old" in p for p in diagnose(BASE, "0.13.9")[1])
    assert not any("too old" in p for p in diagnose(BASE, "0.15.0")[1])


def test_project_mode_and_missing_basics():
    info, problems = diagnose({"LANGSMITH_TRACING": "true", "LANGSMITH_API_KEY": "k", "LANGSMITH_PROJECT": "p"}, "0.3.0")
    assert problems == [] and info["project"] == "p" and info["mode"] == "project addressing"
    assert len(diagnose({}, None)[1]) == 2
    assert any("not enabled" in p for p in diagnose({**BASE, "LANGSMITH_TRACING": "false"}, "0.14.4")[1])


def test_parse_version():
    assert parse_version("0.14.4") == (0, 14, 4) and parse_version("0.14.4rc1") == (0, 14, 4) and parse_version("1.0") == (1, 0)

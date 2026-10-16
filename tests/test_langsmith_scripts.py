from scripts.check_langsmith import diagnose


def test_diagnose_reports_missing_pieces_and_hides_key():
    info, problems = diagnose({})

    assert len(problems) == 2
    assert info["project"] == "default"

    info, problems = diagnose(
        {
            "LANGSMITH_TRACING": "true",
            "LANGSMITH_API_KEY": "lsv2_secret_value",
            "LANGSMITH_PROJECT": "p",
        }
    )

    assert problems == []
    assert info["project"] == "p"
    assert "secret" not in str(info)
    assert "17 chars" in info["api_key"]

    assert diagnose(
        {
            "LANGSMITH_TRACING": "false",
            "LANGSMITH_API_KEY": "k",
        }
    )[1]

    assert diagnose(
        {
            "LANGCHAIN_TRACING_V2": "true",
            "LANGCHAIN_API_KEY": "k",
        }
    )[1] == []
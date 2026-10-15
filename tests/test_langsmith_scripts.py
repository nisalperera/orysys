from pathlib import Path

from scripts.apply_langsmith_fix import apply
from scripts.check_langsmith import diagnose


def test_diagnose_reports_missing_pieces_and_hides_key():
    info, problems = diagnose({})
    assert len(problems) == 2 and info["project"] == "default"
    info, problems = diagnose({"LANGSMITH_TRACING": "true", "LANGSMITH_API_KEY": "lsv2_secret_value", "LANGSMITH_PROJECT": "p"})
    assert problems == [] and info["project"] == "p" and "secret" not in str(info) and "17 chars" in info["api_key"]
    assert diagnose({"LANGSMITH_TRACING": "false", "LANGSMITH_API_KEY": "k"})[1]
    assert diagnose({"LANGCHAIN_TRACING_V2": "true", "LANGCHAIN_API_KEY": "k"})[1] == []


def test_patcher_adds_load_dotenv_once(tmp_path: Path):
    cfg = tmp_path / "config.py"
    cfg.write_text('"""doc"""\nfrom functools import lru_cache\nfrom pydantic_settings import BaseSettings\n')
    assert "patched" in apply(cfg)
    assert "already patched" in apply(cfg)
    text = cfg.read_text()
    assert text.count("load_dotenv()") == 1 and text.index("load_dotenv()") < text.index("pydantic_settings")
    compile(text, "config.py", "exec")
    assert cfg.with_suffix(".py.bak").exists()

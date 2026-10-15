from app.config import Settings
from app.llm import build_llm_kwargs
from app.retrieval.embeddings import format_query



def test_defaults_point_to_openrouter():
    s = Settings(_env_file=None)
    assert s.llm_model == "qwen/qwen3.8-flash"
    assert s.base_url.startswith("https://openrouter.ai")
    assert s.embedding_dim == 4096


def test_thinking_toggle_and_sampling():
    s = Settings(_env_file=None)
    off, on = build_llm_kwargs(s, thinking=False), build_llm_kwargs(s, thinking=True)
    assert off["extra_body"]["reasoning"]["effort"] is "none"
    assert on["extra_body"]["reasoning"]["enabled"] is True
    assert off["temperature"] == 0.7 and on["temperature"] == 0.6
    assert build_llm_kwargs(s, temperature=0.0)["temperature"] == 0.0


def test_query_instruction_format():
    assert format_query("task", "q").startswith("Instruct: task\nQuery:")

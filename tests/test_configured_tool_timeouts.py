from types import SimpleNamespace
from app.tools.authorized_tools import AuthorizedTools


def test_ordinary_tool_timeouts_use_settings_and_research_keeps_separate_limit():
    tools = AuthorizedTools.from_settings(None, None, SimpleNamespace(tool_timeout_sec=7.5))
    for name in ("knowledge_search", "service_catalog", "admin_diagnostics"):
        assert tools.registry.specs[name].timeout == 7.5
    assert tools.registry.specs["python_analysis"].timeout == 150


def test_request_emitter_is_preserved_by_configured_factory():
    emit = lambda event: None
    tools = AuthorizedTools.from_settings(None, None, SimpleNamespace(tool_timeout_sec=8), emit=emit)
    assert tools.emit is emit

"""Validate all anchors before writing. Preserve backups. Run from repo root."""
from pathlib import Path
EDITS = {'app/api/main.py': [('    @app.middleware("http")\n', '    from app.api.t4 import install\n    install(app)\n\n    @app.middleware("http")\n')], 'app/api/wiring.py': [('    def make_engine(emit):\n        return RLMEngine(llm, retriever, catalog, RLMConfig(), emit=emit)\n', '    from app.tools.t4_wiring import T4Tools\n\n    def raw_engine(emit):\n        return RLMEngine(llm, guarded, catalog, RLMConfig(), emit=emit)\n\n    guarded = T4Tools(retriever, raw_engine)\n\n    def make_engine(emit):\n        return T4Tools(retriever, raw_engine, emit=emit)\n'), ('search=retriever.search, make_engine=make_engine,', 'search=guarded.search, make_engine=make_engine,'), ('    service = ChatService(build_graph(deps), deps)\n', '    deps.tools = guarded\n    service = ChatService(build_graph(deps), deps)\n')]}

def apply(root=Path(".")):
    pending={}
    for rel,replacements in EDITS.items():
        p=root/rel
        text=p.read_text()
        for old,new in replacements:
            if new in text: continue
            if old not in text: raise SystemExit(f"Anchor missing in {rel}; no files changed. Inspect local diff.")
            text=text.replace(old,new,1)
        compile(text,rel,"exec")
        pending[p]=text
    for p,text in pending.items():
        if text!=p.read_text():
            p.with_suffix('.py.t4.bak').write_text(p.read_text())
            p.write_text(text)
            print(f"patched {p}")

if __name__=='__main__':
    apply()
    marker = "## T4 security and tool execution"
    section = "\n\n" + marker + "\nSee docs/T4.md for tool permissions, install steps, limits and deferred features.\n"
    for name in ("README.md", "config_guide.md"):
        p = Path(name)
        old = p.read_text() if p.exists() else "# Configuration guide\n"
        if marker not in old: p.write_text(old + section)


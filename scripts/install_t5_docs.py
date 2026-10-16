"""Append T5 config/docs without overwriting prior docs. Run from repository root."""
from pathlib import Path
marker='## T5 Streamlit UI'
section='\n\n'+marker+'\nRun `streamlit run ui/app.py --server.port 8501` alongside the API. See docs/T5.md for configuration, demo authentication and streaming limitations.\n'
for name in ('README.md','config_guide.md'):
    p=Path(name); old=p.read_text() if p.exists() else '# Configuration guide\n'
    if marker not in old: p.write_text(old+section)
p=Path('.env.example');s=p.read_text() if p.exists() else ''
for key,value in [('UI_API_BASE_URL','http://127.0.0.1:8080'),('UI_VIEWER_API_KEY','dev-viewer-key'),('UI_ANALYST_API_KEY','dev-analyst-key'),('UI_ADMIN_API_KEY','dev-admin-key')]:
    if not any(line.startswith(key+'=') for line in s.splitlines()): s+='\n'+key+'='+value
p.write_text(s.rstrip()+'\n')

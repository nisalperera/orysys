# T5 Streamlit interface

Run the existing API on port 8000 (one worker). In a second terminal:

    streamlit run ui/app.py --server.port 3000

Open http://localhost:3000. The Streamlit server calls FastAPI; no browser CORS configuration is required.
Dependencies already in the project: streamlit, httpx, python-dotenv.

Config (add to .env.example and config_guide.md if installing manually):

    UI_API_BASE_URL=http://127.0.0.1:8000
    UI_VIEWER_API_KEY=dev-viewer-key
    UI_ANALYST_API_KEY=dev-analyst-key
    UI_ADMIN_API_KEY=dev-admin-key

If API_TOKENS was customized on the backend, use corresponding keys here. Never put real secrets in .env.example.
Defaults are deliberately demo-only. The role picker selects server-side demo credentials; it is not production login.
Bind Streamlit and FastAPI to loopback for a local demo. Streamlit .env values are loaded at startup, restart to change them.

Features: multi-turn chat, session reset, identity isolation, citations, live state/node/retrieval/memory/validation/tool
and RLM events. Provisional streaming can be enabled but is off by default because tokens precede backend validation.
The final event always replaces any provisional content. Research currently streams activity, not answer tokens.
Role switching creates a new backend session. Browser refresh/restart can lose local chat state.

Test: PYTHONPATH=. pytest -q tests/test_ui_client.py
Manual: viewer runbook query, follow-up escalation question, analyst research query, blocked input, rate-limit response.
Limitations: mock enterprise tools still require /tools/execute; no autonomous graph tool-selection added by this UI.
No arbitrary local shell, file edits or git tools are exposed. SSE uses POST via httpx from the Streamlit server.

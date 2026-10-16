# Lanka Meridian Bank AI Assistant (assessment POC)

Enterprise knowledge assistant: LangGraph multi-agent orchestration, hybrid RAG on Pinecone,
simplified Recursive Language Model (RLM) research, RBAC, guardrails, LangSmith tracing.
Runs on local models via vLLM: Qwen3-8B-AWQ (chat) and Qwen3-Embedding-0.6B (embeddings). See `docs/vllm_serving.md`.
Status: T0 complete (scaffold, mock corpus, ingestion, local LLM config). See `docs/ASSUMPTIONS.md`.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# start both vLLM servers first (docs/vllm_serving.md)
cp .env.example .env            # add Pinecone and LangSmith keys
python scripts/generate_mock_docs.py   # regenerates data/docs (36 docs)
python -m pytest -q
python -m scripts.ingest --recreate    # chunk -> embed -> store in Pinecone
```

## Layout
- `app/config.py`, `app/logging_config.py`: settings and structured JSON logs
- `app/llm.py`: vLLM chat model factory (thinking toggle, health check)
- `app/retrieval/`: loader, chunking, embeddings client, hybrid search (next)
- `app/graph`, `app/agents`: LangGraph state and agents (next)
- `app/tools`, `app/security`, `app/auth`: tool registry, guardrails, RBAC (next)
- `ui/`: Streamlit app (next)
- `data/docs`: mock corpus, with recurring incident root causes for the RLM demo

## Corpus
36 markdown docs: 11 incidents (4 root-cause families, plus one older and one non-payment distractor),
6 runbooks, 5 architecture docs, 5 product specs, 6 meeting notes, 3 policies.
`MTG-006` carries a prompt-injection payload as a security test fixture.


## T5 Streamlit UI
Run `streamlit run ui/app.py --server.port 8501` alongside the API. See docs/T5.md for configuration, demo authentication and streaming limitations.


## Acceptance reliability fixes
See docs/reliability_fixes.md. No new settings.

# Configuration guide

See [runtime integration notes](docs/runtime_integration.md) for the shared model endpoint template, effective tool timeouts, public diagnostics and final validation status.

See [security and reliability update notes](docs/security_review_changes.md) for shared model endpoint behavior, sanitized activity errors, tracing, and validation limitations.

## Configuration sources

Application settings are defined in `app/config.py`.

The application loads `.env` into the process environment for integrations
that read environment variables directly, including tracing integrations.

Existing process environment values take priority over values loaded by
`python-dotenv`.

Never commit the real `.env`.

## Ports

| Component | Local address | Compose address |
|---|---|---|
| API | http://127.0.0.1:8000 | http://api:8000 |
| UI | http://127.0.0.1:3000 | Published on host port 3000 |

Local UI configuration:

```dotenv
UI_API_BASE_URL=http://127.0.0.1:8000
```

Compose overrides this with:

```dotenv
UI_API_BASE_URL=http://api:8000
```

The Compose file is `docker-compose.yml`.

## Model provider

```dotenv
BASE_URL=
API_KEY=
LLM_MODEL=
LLM_MAX_TOKENS=2048
LLM_TIMEOUT_SEC=60
LLM_MAX_RETRIES=2
```

Use the currently working provider configuration.

Local vLLM examples and hosted-model defaults in the repository are
alternatives, not evidence of the active runtime provider.

## Embeddings

```dotenv
EMBEDDING_MODEL=
EMBEDDING_DIM=
EMBEDDING_QUERY_INSTRUCTION=Given a user question about bank internal documents, retrieve relevant passages
```

The model, dimensions and formatting must remain compatible with indexed
document embeddings.

Separate chat/embedding endpoint routing must be verified in:

- `app/llm.py`
- `app/retrieval/embeddings.py`

Do not assume an unsupported `EMBEDDING_BASE_URL` setting exists.

## Host-run models and Docker

Container localhost is not the Docker host.

The API Compose service includes a host-gateway mapping for
`host.docker.internal`.

Use an appropriate reachable host endpoint when models run on the host.
The model server must listen on an interface reachable from Docker.

API host port 8000 cannot also be occupied by a host model server on the
same address. Resolve port conflicts explicitly.

Do not expose model endpoints publicly without appropriate protections.

## Pinecone

```dotenv
PINECONE_API_KEY=
PINECONE_INDEX=bank-kb
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1
```

Changing provisioning values does not migrate an existing index.

Do not recreate an index during normal startup.

## Retrieval and corpus

```dotenv
DOCS_DIR=data/docs
BM25_PARAMS_PATH=data/bm25_params.json
HYBRID_ALPHA=0.6
RETRIEVAL_MIN_SCORE=0.3
RETRIEVAL_MAX_PER_DOC=2
EMBEDDING_CACHE_SIZE=256
```

Compose mounts `./data` read-only and overrides artifact paths:

```dotenv
DOCS_DIR=/app/data/docs
BM25_PARAMS_PATH=/app/data/bm25_params.json
```

The local catalog, saved BM25 parameters and indexed corpus must agree.

The current retrieval factory falls back to dense-only retrieval if BM25
parameters cannot be loaded. This is degraded operation.

Do not independently refit BM25 against a changed corpus while retaining
old sparse document vectors.

## Rate limiting and tools

```dotenv
RATE_LIMIT_CAPACITY=10
RATE_LIMIT_REFILL_PER_SEC=0.5
TOOL_TIMEOUT_SEC=15
```

Rate limits are per user.

Run one API worker for the current process-local state design.

Registered tools may define specific timeout behavior; review tool
registration when changing timeouts.

## Demo UI identities

```dotenv
UI_VIEWER_API_KEY=dev-viewer-key
UI_ANALYST_API_KEY=dev-analyst-key
UI_ADMIN_API_KEY=dev-admin-key
```

These values configure the UI client, not the backend user registry.

The identity selector is demo-only authentication. Keep published demo
ports bound to host loopback.

## LangSmith

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=[https://apac.api.smith.langchain.com](https://apac.api.smith.langchain.com)
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=orysys
```

Use the endpoint appropriate to the actual workspace.

Verify real traces after starting the application.

Do not assume `LANGSMITH_AGENT_ID` or `LANGSMITH_AGENT_ENVIRONMENT`
changes application metadata without checking how they are consumed.

Tracing can transmit prompts, retrieved evidence and outputs.
Use synthetic data unless external processing is approved.

## Start locally

API:

```bash
python -m uvicorn app.api.main:app \
  --host 127.0.0.1 --port 8000 --workers 1
```

UI:

```bash
UI_API_BASE_URL=http://127.0.0.1:8000 \
python -m streamlit run ui/app.py \
  --server.address 127.0.0.1 --server.port 3000
```

## Start with Compose

```bash
docker compose config --quiet
docker compose build api ui
docker compose up -d
docker compose ps
```

Do not publish full resolved Compose output without checking for secrets.

## Health and validation

- API liveness: `/openapi.json`
- API provider check: `/health`
- Streamlit health: `/_stcore/health`

Inspect `/health` JSON status; HTTP success alone does not prove readiness.

Run:

```bash
python -m pytest -q
python -m scripts.run_failure_drills
```

Container health does not verify retrieval quality or LangSmith tracing.

## Related documentation

- `README.md`
- `docs/ASSUMPTIONS.md`
- `docs/T4.md`
- `docs/T5.md`
- `docs/T6_failure_drills.md`
- `docs/reliability_fixes.md`
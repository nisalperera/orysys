# Local model serving and provider compatibility

## Supported application contract

The current chat and embedding clients share `BASE_URL` and `API_KEY`.
The selected endpoint must support both the configured chat model and embedding model.
Independent `LLM_BASE_URL` or `EMBEDDING_BASE_URL` settings are not implemented.

The example environment describes a hosted compatible endpoint with model placeholders.
Use your tested provider/model configuration; the example is not ready-to-run credentials.
Do not overwrite a working `.env` merely to match a documentation example.

## Historical two-server example is not wired

Earlier instructions described a chat-only vLLM server on port 8000 and a separate
embedding server on port 8001. That is not a directly supported application topology:

- The FastAPI application now occupies host port 8000.
- One shared BASE_URL does not automatically route calls to two model servers.
- A chat-only vLLM process does not automatically serve a different embedding model.

To use two local model processes, implement separate client endpoint configuration
or operate a compatible gateway that routes the two API/model requests. Neither
local gateway provisioning nor independent endpoint wiring is supplied by this guide.
Do not treat those options as implemented features.

## Ports and container networking

- API: host/container port 8000.
- Streamlit: host/container port 3000.
- Compose UI backend: http://api:8000.
- Host model services need distinct available host ports.
- Container localhost is the container, not the Docker host.
- The Compose host-gateway mapping supports host.docker.internal when the host
  service listens on a reachable interface. Apply appropriate firewall controls.

## Embedding/index compatibility

Use the embedding model, dimensions, query formatting and BM25 artifact matching
the existing Pinecone index. A historical 1024-dimension local-model example is
not proof of the active index configuration.

A model change requires an explicit migration plan, including compatibility checks
and re-embedding/reindexing where necessary. Do not use --recreate as ordinary
startup or as an automatic response to a model error. Preserve existing data until
an intentional migration has been reviewed.

## Verification

1. Check the configured endpoint's model availability using approved credentials.
2. Verify an actual chat request and an actual embedding request succeed.
3. Confirm embedding vector length matches the existing index.
4. Confirm hybrid retrieval loads the matching saved BM25 parameters.
5. Run a cited question and inspect LangSmith traces.

The public /health endpoint is intentionally generic. Successful model-list health
alone does not prove generation, embeddings or Pinecone readiness.

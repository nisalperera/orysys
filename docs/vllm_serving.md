# Local model serving (vLLM)

Two OpenAI-compatible servers: chat (Qwen3-8B-AWQ, port 8000) and embeddings (Qwen3-Embedding-0.6B, port 8001).
Split GPU memory between them with `--gpu-memory-utilization`.

## Chat model
```bash
vllm serve Qwen/Qwen3-8B-AWQ \
  --port 8000 \
  --max-model-len 16384 \
  --gpu-memory-utilization 0.70 \
  --enable-auto-tool-choice --tool-call-parser hermes \
  --reasoning-parser qwen3
```
- `--enable-auto-tool-choice` with `--tool-call-parser hermes` enables function calling (Qwen3 uses Hermes style tool calls).
- `--reasoning-parser qwen3` separates `<think>` output into `reasoning_content`. Older vLLM versions name this parser `deepseek_r1`.
- Thinking is toggled per request by the app (`app/llm.py`) via `chat_template_kwargs.enable_thinking`.

## Embedding model
```bash
vllm serve Qwen/Qwen3-Embedding-0.6B --port 8001 --gpu-memory-utilization 0.15 --runner pooling --convert embed
```
Older vLLM versions use `--task embed` instead of `--runner pooling --convert embed`. Check `vllm serve --help` for your version.

## Verify
```bash
curl localhost:8000/v1/models
curl localhost:8001/v1/embeddings -H 'Content-Type: application/json' \
  -d '{"model":"Qwen/Qwen3-Embedding-0.6B","input":"hello"}'
```
The returned vector length must equal `EMBEDDING_DIM` (1024). Changing embedding model or dimension requires `python -m scripts.ingest --recreate`.

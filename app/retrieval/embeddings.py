"""Dense embeddings via a local vLLM embedding server (RAG stage: embed).

Qwen3-Embedding expects queries to carry a task instruction while documents are
embedded as plain text. vLLM's OpenAI endpoint has no instruction field, so the
prefix is added here.
"""

from tqdm import tqdm
from openai import AsyncOpenAI

from app.config import Settings, get_settings

BATCH = 32


def format_query(instruction: str, query: str) -> str:
    return f"Instruct: {instruction}\nQuery:{query}"


def _client(s: Settings) -> AsyncOpenAI:
    return AsyncOpenAI(base_url=s.base_url, api_key=s.api_key)


async def _embed(texts: list[str]) -> list[list[float]]:
    s = get_settings()
    client, out = _client(s), []
    for text in tqdm(texts, desc="Embedding", unit="text", leave=False, colour="green"):
        resp = await client.embeddings.create(
            model=s.embedding_model, 
            input=text,
        )
        out.extend(d.embedding for d in resp.data)
    if out and len(out[0]) != s.embedding_dim:
        raise ValueError(f"Embedding dim {len(out[0])} != configured {s.embedding_dim}")
    return out


async def embed_documents(texts: list[str]) -> list[list[float]]:
    return await _embed(texts)


async def embed_query(query: str) -> list[float]:
    s = get_settings()
    return (await _embed([format_query(s.embedding_query_instruction, query)]))[0]

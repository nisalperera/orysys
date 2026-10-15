"""Central configuration. All thresholds are env-configurable (see .env.example)."""
from functools import lru_cache

from dotenv import load_dotenv

# LangSmith and LangChain read os.environ, while pydantic-settings only fills the Settings object.
load_dotenv()  # shell variables win over .env
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM && Embeddings
    base_url: str = model_config.get("BASE_URL", "https://openrouter.ai/api/v1")
    api_key: str = model_config.get("API_KEY", "EMPTY")

    # LLM
    llm_model: str = model_config.get("LLM_MODEL", "qwen/qwen3.8-flash")
    llm_max_tokens: int = model_config.get("LLM_MAX_TOKENS", 2048)
    llm_timeout_sec: float = model_config.get("LLM_TIMEOUT_SEC", 60.0)
    llm_max_retries: int = model_config.get("LLM_MAX_RETRIES", 2)

    # Embeddings
    embedding_model: str = model_config.get("EMBEDDING_MODEL", "qwen/qwen3-embedding-8b")
    embedding_dim: int = model_config.get("EMBEDDING_DIM", 4096)
    embedding_query_instruction: str = model_config.get("EMBEDDING_QUERY_INSTRUCTION", "Given a user question about bank internal documents, retrieve relevant passages")

    pinecone_api_key: str = ""
    pinecone_index: str = "bank-kb"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    hybrid_alpha: float = 0.6  # 1.0 = dense only, 0.0 = sparse only
    rate_limit_capacity: int = 10
    rate_limit_refill_per_sec: float = 0.5
    tool_timeout_sec: float = 15.0

    docs_dir: str = "data/docs"
    bm25_params_path: str = "data/bm25_params.json"
    bank_name: str = "Lanka Meridian Bank"

    retrieval_min_score: float = 0.3
    retrieval_max_per_doc: int = 2
    embedding_cache_size: int = 256


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Run the RLM against the real stack (Pinecone + your LLM) and print activity events.

python -m scripts.rlm_demo analyst1 "Summarize all outage reports related to payment failures during the last year and identify recurring root causes"

Runs a preflight first, so a wrong model id or key stops here with a clear message and does not burn requests.
"""
import argparse, asyncio, json

from app.auth.models import USERS
from app.config import get_settings
from app.llm import ensure_llm_ready, get_chat_model
from app.logging_config import setup_logging
from app.retrieval.factory import build_retriever
from app.rlm.catalog import Catalog
from app.rlm.executor import RLMEngine
from app.rlm.llm_adapter import from_langchain


def show(ev: dict) -> None:
    extra = {k: v for k, v in ev.items() if k not in ("agent", "stage", "type")}
    print(f"[rlm] {ev['type']:<14} {json.dumps(extra, default=str)[:300]}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("user", choices=USERS)
    ap.add_argument("question")
    a = ap.parse_args()
    setup_logging()
    await ensure_llm_ready()
    engine = RLMEngine(from_langchain(get_chat_model(thinking=False, streaming=False)), build_retriever(),
                       Catalog.from_dir(get_settings().docs_dir), emit=show)
    res = await engine.run(USERS[a.user], a.question)
    print("\n=== ANSWER ===\n" + res.answer)
    print("\n=== META ===")
    print(json.dumps(res.model_dump(exclude={"answer", "analysis"}), indent=2, default=str))
    print(json.dumps(res.analysis, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

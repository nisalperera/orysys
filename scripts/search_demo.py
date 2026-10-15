"""Try hybrid retrieval from the CLI.

python -m scripts.search_demo viewer1 "payment failures connection pool" --from 2025-10-16
python -m scripts.search_demo admin1 "executive compensation" --types meeting_notes --alpha 0.3
"""
import argparse, asyncio, json

from app.auth.models import USERS
from app.logging_config import setup_logging
from app.retrieval.factory import build_retriever
from app.retrieval.schemas import SearchRequest


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("user", choices=USERS)
    ap.add_argument("query")
    ap.add_argument("--types", nargs="*")
    ap.add_argument("--dept")
    ap.add_argument("--from", dest="date_from")
    ap.add_argument("--to", dest="date_to")
    ap.add_argument("--alpha", type=float)
    ap.add_argument("--top-k", type=int, default=6)
    a = ap.parse_args()
    setup_logging()
    req = SearchRequest(query=a.query, top_k=a.top_k, document_types=a.types, department=a.dept,
                        date_from=a.date_from, date_to=a.date_to, alpha=a.alpha)
    retriever = build_retriever()
    for run in (1, 2):  # second run shows the embedding cache effect
        res = await retriever.search(USERS[a.user], req)
        print(f"run {run}: embed={res.embed_ms}ms query={res.query_ms}ms total={res.latency_ms}ms")
    print(json.dumps(res.model_dump(exclude={"hits"}), indent=2, default=str))
    if res.no_relevant_results:
        print("NO RELEVANT RESULTS (all candidates below min_score)")
    for h in res.hits:
        print(f"{h.score:8.4f}  [{h.access_level:12}] {h.chunk_id:18} {h.title[:70]}")


if __name__ == "__main__":
    asyncio.run(main())

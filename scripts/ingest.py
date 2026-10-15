"""Ingest corpus into Pinecone with hybrid vectors.

RAG stages covered here: chunk -> embed (dense via local vLLM + sparse BM25) -> store.
Index metric must be dotproduct for hybrid. Namespace = document_type
(lets the RLM agent target one corpus slice); access control is enforced by
metadata filter on access_level at query time.

Usage: python -m scripts.ingest [--recreate]
"""
import argparse, asyncio, logging
from collections import defaultdict

from pinecone import Pinecone, ServerlessSpec
from pinecone_text.sparse import BM25Encoder

from app.config import get_settings
from app.logging_config import setup_logging
from app.retrieval.embeddings import embed_documents
from app.retrieval.loader import chunk_document, load_all

log = logging.getLogger("ingest")


def ensure_index(pc: Pinecone, name: str, dim: int, cloud: str, region: str, recreate: bool) -> None:
    existing = {i["name"] for i in pc.list_indexes()}
    if name in existing and recreate:
        pc.delete_index(name)
        existing.discard(name)
    if name not in existing:
        pc.create_index(name=name, dimension=dim, metric="dotproduct",
                        spec=ServerlessSpec(cloud=cloud, region=region))
        log.info("created index %s", name)


async def main(recreate: bool) -> None:
    s = get_settings()
    setup_logging()
    docs = load_all(s.docs_dir)
    chunks = [c for d in docs for c in chunk_document(d)]
    log.info("loaded %d docs, %d chunks", len(docs), len(chunks))

    bm25 = BM25Encoder()
    bm25.fit([c.text for c in chunks])
    bm25.dump(s.bm25_params_path)

    dense = await embed_documents([c.text for c in chunks])
    sparse = bm25.encode_documents([c.text for c in chunks])

    pc = Pinecone(api_key=s.pinecone_api_key)
    ensure_index(pc, s.pinecone_index, s.embedding_dim, s.pinecone_cloud, s.pinecone_region, recreate)
    index = pc.Index(s.pinecone_index)

    by_ns = defaultdict(list)
    for c, d, sp in zip(chunks, dense, sparse):
        by_ns[c.metadata["document_type"]].append(
            {"id": c.chunk_id, "values": d, "sparse_values": sp, "metadata": c.metadata})
    for ns, vecs in by_ns.items():
        for i in range(0, len(vecs), 100):
            index.upsert(vectors=vecs[i:i + 100], namespace=ns)
        log.info("upserted %d vectors into namespace %s", len(vecs), ns)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--recreate", action="store_true")
    asyncio.run(main(ap.parse_args().recreate))

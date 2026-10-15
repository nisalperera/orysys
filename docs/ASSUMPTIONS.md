# Assumptions and trade-offs (living document)

1. Fictional company: Lanka Meridian Bank. All data is synthetic.
2. Pinecone namespace = `document_type`. Access control uses the `access_level` metadata filter,
   not namespaces, because access tiers are hierarchical (a role sees its tier and all lower tiers).
3. Role to access tiers (planned): viewer = public, internal; analyst = + confidential; admin = + restricted.
4. Hybrid search: dense (Qwen3-Embedding-0.6B served by vLLM, 1024 dims) + sparse BM25 (pinecone-text) in one dotproduct index,
   fused with a configurable alpha (`HYBRID_ALPHA`).
5. Chunking is heading-aware with title prefix so each chunk is self-describing for citation.
6. Mock corpus is generated deterministically by script (reproducible, no LLM variance).
7. "Last year" in the RLM demo is relative to the assessment date (Oct 2026), so INC-2024-052 must be filtered out.
8. Demo video length in the brief reads "45 minutes", assumed to mean about 5 minutes.
9. LLM: Qwen3-8B-AWQ on a local vLLM server. Rationale: no data leaves the machine (suits a banking scenario),
   zero marginal cost, native tool calling and a switchable thinking mode. Trade-off: weaker instruction following
   and tool-call reliability than frontier models, so tool parameters are always validated with pydantic and
   graph nodes use constrained, short prompts.
10. One chat model serves all agents. Routing and validation run non-thinking, research and final answer may use thinking.
11. Embeddings run on a second vLLM server; queries get the Qwen3-Embedding instruction prefix, documents do not.

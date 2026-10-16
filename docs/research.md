# T3: Recursive Language Model (RLM) and Python analysis tool

Question: "Summarize all outage reports related to payment failures during the last year and identify recurring root causes."

1. explore: `Catalog.stats()` (counts, date range). No document content reaches an LLM.
2. plan: the LLM writes a 4 statement Python program (select, batches, map_analyze, reduce_all). `ast` validation, never `exec`.
   Invalid twice -> deterministic fallback plan.
3. select: plain Python filter over metadata (type, date, topic keywords on titles, RBAC tiers).
4. batch: documents split into batches (default 3).
5. analyse: one sub-agent per batch, in parallel (semaphore), over targeted sections from Pinecone (hybrid search filtered by doc_ids).
   Evidence over the context budget triggers a recursive split (max depth 2) without a second retrieval.
6. aggregate: `app/tools/python_analysis.py` computes counts, downtime, recurring causes. Hierarchical LLM reduce writes the answer
   using those numbers. Failed batches and reduce failures degrade gracefully and are reported.

Guardrails inside the RLM: retrieved text is sanitised for instruction-like lines, sub-agent JSON is validated, findings for unknown
documents are dropped, evidence ids must come from retrieved chunks, and document ids in the final answer are checked against the selection.

Trade-offs: topic filter is keyword on titles (use match_in="any" for bodies), the catalog is built from local files, numeric facts are
regex-extracted from document text. Production would use structured metadata fields.

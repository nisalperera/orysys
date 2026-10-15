from app.retrieval.loader import chunk_document, load_all


def test_all_docs_load_and_chunk():
    docs = load_all("data/docs")
    assert len(docs) >= 30
    for d in docs:
        chunks = chunk_document(d)
        assert chunks, d.doc_id
        for c in chunks:
            assert c.metadata["access_level"] in {"public", "internal", "confidential", "restricted"}
            assert c.metadata["doc_id"] == d.doc_id
            assert c.metadata["created_ts"] > 0


def test_incident_has_root_cause_chunk():
    docs = {d.doc_id: d for d in load_all("data/docs")}
    chunks = chunk_document(docs["INC-2026-007"])
    assert any("Root cause" in c.metadata["section"] for c in chunks)

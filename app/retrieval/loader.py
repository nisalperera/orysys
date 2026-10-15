"""Document loading and section-aware chunking (RAG stage: chunk)."""
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

_FM = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
_HEADING = re.compile(r"^(#{1,3})\s+(.*)$", re.MULTILINE)


@dataclass
class Document:
    doc_id: str
    title: str
    department: str
    document_type: str
    access_level: str
    created_date: str
    body: str


@dataclass
class Chunk:
    chunk_id: str
    text: str
    metadata: dict = field(default_factory=dict)


def load_document(path: Path) -> Document:
    m = _FM.match(path.read_text(encoding="utf-8"))
    if not m:
        raise ValueError(f"Missing front matter: {path}")
    meta = yaml.safe_load(m.group(1))
    return Document(body=m.group(2).strip(), **{k: str(v) for k, v in meta.items()})


def load_all(docs_dir: str) -> list[Document]:
    return [load_document(p) for p in sorted(Path(docs_dir).glob("*.md"))]


def _to_ts(date_str: str) -> int:
    return int(datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def chunk_document(doc: Document, max_chars: int = 900) -> list[Chunk]:
    """Split on markdown headings, then pack paragraphs up to max_chars.

    Every chunk carries the document title as a prefix so that dense and sparse
    signals both see document context, and full metadata for filtering/attribution.
    """
    parts, last, current = [], 0, "Introduction"
    for m in _HEADING.finditer(doc.body):
        if m.start() > last:
            parts.append((current, doc.body[last:m.start()].strip()))
        current, last = m.group(2).strip(), m.end()
    parts.append((current, doc.body[last:].strip()))

    chunks: list[Chunk] = []
    for section, text in parts:
        if not text:
            continue
        buf = ""
        for para in re.split(r"\n\s*\n", text):
            if buf and len(buf) + len(para) > max_chars:
                chunks.append(_mk(doc, section, buf, len(chunks)))
                buf = ""
            buf = f"{buf}\n\n{para}".strip()
        if buf:
            chunks.append(_mk(doc, section, buf, len(chunks)))
    return chunks


def _mk(doc: Document, section: str, text: str, idx: int) -> Chunk:
    full = f"{doc.title} | {section}\n{text}"
    return Chunk(
        chunk_id=f"{doc.doc_id}#{idx}",
        text=full,
        metadata={
            "doc_id": doc.doc_id, "title": doc.title, "section": section,
            "department": doc.department, "document_type": doc.document_type,
            "access_level": doc.access_level, "created_date": doc.created_date,
            "created_ts": _to_ts(doc.created_date), "text": full,
        },
    )

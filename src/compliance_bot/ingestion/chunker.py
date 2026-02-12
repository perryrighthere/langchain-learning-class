"""Week 2 deterministic chunking for policy documents."""

from __future__ import annotations

from hashlib import sha256
from typing import Sequence

from compliance_bot.schemas.ingestion import ChunkRecord, LoadedDocument

DEFAULT_CHUNK_SIZE = 700
DEFAULT_CHUNK_OVERLAP = 120


def _normalize_text(text: str) -> str:
    """Normalize whitespace so chunk IDs remain stable across runs."""

    return " ".join(text.split())


def _split_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split text into stable fixed-size chunks with overlap."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and < chunk_size")

    normalized = _normalize_text(text)
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    total = len(normalized)
    while start < total:
        end = min(start + chunk_size, total)
        candidate = normalized[start:end].strip()
        if candidate:
            chunks.append(candidate)
        if end == total:
            break
        start = end - chunk_overlap

    return chunks


def _build_chunk_id(
    *,
    version_tag: str,
    doc_id: str,
    chunk_index: int,
    content: str,
) -> str:
    raw = f"{version_tag}:{doc_id}:{chunk_index}:{content}"
    return sha256(raw.encode("utf-8")).hexdigest()[:16]


def chunk_document(
    document: LoadedDocument,
    *,
    version_tag: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[ChunkRecord]:
    """Chunk one document into deterministic chunk records."""

    doc_id = document.metadata.get("doc_id", "unknown-doc")
    text_chunks = _split_text(
        document.content,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    records: list[ChunkRecord] = []
    for index, text_chunk in enumerate(text_chunks):
        records.append(
            ChunkRecord(
                chunk_id=_build_chunk_id(
                    version_tag=version_tag,
                    doc_id=doc_id,
                    chunk_index=index,
                    content=text_chunk,
                ),
                doc_id=doc_id,
                version_tag=version_tag,
                chunk_index=index,
                content=text_chunk,
                metadata={**document.metadata, "source_path": document.source_path},
            )
        )
    return records


def chunk_corpus(
    documents: Sequence[LoadedDocument],
    *,
    version_tag: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[ChunkRecord]:
    """Chunk a corpus with deterministic document ordering."""

    ordered_documents = sorted(
        documents,
        key=lambda item: (item.metadata.get("doc_id", ""), item.source_path),
    )

    records: list[ChunkRecord] = []
    for document in ordered_documents:
        records.extend(
            chunk_document(
                document,
                version_tag=version_tag,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )
    return records

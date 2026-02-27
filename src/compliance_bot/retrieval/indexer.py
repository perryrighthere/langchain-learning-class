"""Week 3 retrieval indexing utilities."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

from compliance_bot.schemas.ingestion import ChunkRecord, CorpusManifest

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class IndexedChunk(BaseModel):
    """Chunk record with token set cached for scoring."""

    chunk_id: str = Field(..., min_length=1)
    doc_id: str = Field(..., min_length=1)
    version_tag: str = Field(..., min_length=1)
    chunk_index: int = Field(..., ge=0)
    content: str = Field(..., min_length=1)
    metadata: dict[str, str] = Field(default_factory=dict)
    tokens: list[str] = Field(default_factory=list)
    vector: list[float] | None = None


class RetrievalIndex(BaseModel):
    """In-memory index used by the Week 3 retriever."""

    version_tag: str = Field(..., min_length=1)
    chunks: list[IndexedChunk] = Field(default_factory=list)
    token_to_chunk_ids: dict[str, list[str]] = Field(default_factory=dict)
    chunk_lookup: dict[str, IndexedChunk] = Field(default_factory=dict)
    vector_dim: int = Field(default=0, ge=0)


class EmbeddingProvider(Protocol):
    """Embedding provider protocol used by retrieval index builder."""

    provider_name: str
    model: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per text."""


def tokenize(text: str) -> list[str]:
    """Tokenize plain text into lowercase alphanumeric terms."""

    return _TOKEN_PATTERN.findall(text.lower())


def load_manifest(path: Path) -> CorpusManifest:
    """Load a Week 2 manifest artifact from disk."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    return CorpusManifest.model_validate(payload)


def _to_indexed_chunk(chunk: ChunkRecord, *, vector: list[float] | None = None) -> IndexedChunk:
    token_set = sorted(set(tokenize(chunk.content)))
    return IndexedChunk(
        chunk_id=chunk.chunk_id,
        doc_id=chunk.doc_id,
        version_tag=chunk.version_tag,
        chunk_index=chunk.chunk_index,
        content=chunk.content,
        metadata=chunk.metadata,
        tokens=token_set,
        vector=vector,
    )


def build_retrieval_index(
    manifest: CorpusManifest,
    *,
    embedding_provider: EmbeddingProvider | None = None,
) -> RetrievalIndex:
    """Build deterministic in-memory retrieval index from a corpus manifest."""

    ordered_chunks = sorted(
        manifest.chunks,
        key=lambda item: (item.doc_id, item.chunk_index, item.chunk_id),
    )

    vectors: list[list[float] | None]
    if embedding_provider is None:
        vectors = [None] * len(ordered_chunks)
    else:
        raw_vectors = embedding_provider.embed_documents(
            [chunk.content for chunk in ordered_chunks]
        )
        if len(raw_vectors) != len(ordered_chunks):
            raise ValueError("embedding provider returned unexpected vector count")
        vectors = [list(vector) for vector in raw_vectors]

    indexed_chunks = [
        _to_indexed_chunk(chunk, vector=vector)
        for chunk, vector in zip(ordered_chunks, vectors, strict=True)
    ]
    token_to_chunk_ids: dict[str, list[str]] = {}
    chunk_lookup: dict[str, IndexedChunk] = {}

    for chunk in indexed_chunks:
        chunk_lookup[chunk.chunk_id] = chunk
        for token in chunk.tokens:
            token_to_chunk_ids.setdefault(token, []).append(chunk.chunk_id)

    for chunk_ids in token_to_chunk_ids.values():
        chunk_ids.sort()

    return RetrievalIndex(
        version_tag=manifest.version_tag,
        chunks=indexed_chunks,
        token_to_chunk_ids=token_to_chunk_ids,
        chunk_lookup=chunk_lookup,
        vector_dim=len(indexed_chunks[0].vector) if indexed_chunks and indexed_chunks[0].vector else 0,
    )

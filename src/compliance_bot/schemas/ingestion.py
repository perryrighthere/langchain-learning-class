"""Week 2 ingestion schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class LoadedDocument(BaseModel):
    """Sanitized source document loaded from disk."""

    content: str = Field(..., min_length=1)
    metadata: dict[str, str] = Field(default_factory=dict)
    source_path: str = Field(..., min_length=1)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("content must not be blank")
        return normalized


class ChunkRecord(BaseModel):
    """Chunk-level record emitted by Week 2 chunking."""

    chunk_id: str = Field(..., min_length=8)
    doc_id: str = Field(..., min_length=1)
    version_tag: str = Field(..., min_length=1)
    chunk_index: int = Field(..., ge=0)
    content: str = Field(..., min_length=1)
    metadata: dict[str, str] = Field(default_factory=dict)


class MetadataCoverageReport(BaseModel):
    """Coverage report for required metadata keys."""

    total_documents: int = Field(..., ge=0)
    valid_documents: int = Field(..., ge=0)
    coverage_by_key: dict[str, float] = Field(default_factory=dict)


class CorpusManifest(BaseModel):
    """Deterministic corpus manifest for versioned snapshots."""

    version_tag: str = Field(..., min_length=1)
    manifest_hash: str = Field(..., min_length=32)
    doc_count: int = Field(..., ge=0)
    chunk_count: int = Field(..., ge=0)
    metadata_coverage: dict[str, float] = Field(default_factory=dict)
    chunks: list[ChunkRecord] = Field(default_factory=list)

"""Week 2 manifest builder for reproducible corpus snapshots."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any, Sequence

from compliance_bot.schemas.ingestion import (
    ChunkRecord,
    CorpusManifest,
    MetadataCoverageReport,
)


def _canonical_chunk_payload(chunk: ChunkRecord) -> dict[str, Any]:
    """Return a stable chunk payload used for manifest hashing."""

    return {
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "version_tag": chunk.version_tag,
        "chunk_index": chunk.chunk_index,
        "content_sha256": sha256(chunk.content.encode("utf-8")).hexdigest(),
        "metadata": chunk.metadata,
    }


def _build_manifest_hash(chunks: Sequence[ChunkRecord], *, version_tag: str) -> str:
    """Compute deterministic manifest hash from canonical chunk payloads."""

    canonical_chunks = [
        _canonical_chunk_payload(chunk)
        for chunk in sorted(
            chunks,
            key=lambda item: (item.doc_id, item.chunk_index, item.chunk_id),
        )
    ]
    payload = {
        "version_tag": version_tag,
        "chunks": canonical_chunks,
    }
    digest_input = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(digest_input.encode("utf-8")).hexdigest()


def build_manifest(
    chunks: Sequence[ChunkRecord],
    *,
    version_tag: str,
    metadata_report: MetadataCoverageReport,
) -> CorpusManifest:
    """Build deterministic corpus manifest model."""

    ordered_chunks = sorted(
        chunks,
        key=lambda item: (item.doc_id, item.chunk_index, item.chunk_id),
    )

    return CorpusManifest(
        version_tag=version_tag,
        manifest_hash=_build_manifest_hash(ordered_chunks, version_tag=version_tag),
        doc_count=len({chunk.doc_id for chunk in ordered_chunks}),
        chunk_count=len(ordered_chunks),
        metadata_coverage=metadata_report.coverage_by_key,
        chunks=ordered_chunks,
    )


def write_manifest(manifest: CorpusManifest, output_dir: Path) -> Path:
    """Persist manifest JSON under a deterministic filename."""

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"manifest-{manifest.version_tag}.json"

    serialized = json.dumps(manifest.model_dump(), indent=2, sort_keys=True)
    path.write_text(f"{serialized}\n", encoding="utf-8")
    return path

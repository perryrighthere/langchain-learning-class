"""Week 3 indexer tests."""

from __future__ import annotations

from compliance_bot.retrieval.indexer import build_retrieval_index
from compliance_bot.schemas.ingestion import ChunkRecord, CorpusManifest


class _MockEmbeddingProvider:
    provider_name = "siliconflow"
    model = "mock"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 1.0] for text in texts]


def test_build_index_with_embedding_provider_sets_vectors() -> None:
    manifest = CorpusManifest(
        version_tag="week-03-v1",
        manifest_hash="x" * 64,
        doc_count=1,
        chunk_count=1,
        metadata_coverage={},
        chunks=[
            ChunkRecord(
                chunk_id="chunk-0001",
                doc_id="doc-1",
                version_tag="week-03-v1",
                chunk_index=0,
                content="Expense approvals require manager signoff.",
                metadata={"jurisdiction": "US"},
            )
        ],
    )

    index = build_retrieval_index(manifest, embedding_provider=_MockEmbeddingProvider())

    assert index.vector_dim == 2
    assert index.chunks[0].vector is not None
    assert len(index.chunks[0].vector) == 2

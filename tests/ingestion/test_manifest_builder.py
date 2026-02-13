"""Week 2 manifest integration tests."""

from __future__ import annotations

import json
from pathlib import Path

from compliance_bot.ingestion.pipeline import build_corpus_snapshot


def _write_policy(path: Path, *, doc_id: str, content: str) -> None:
    payload = {
        "content": content,
        "metadata": {
            "doc_id": doc_id,
            "effective_date": "2026-02-01",
            "owner": "compliance-team",
            "jurisdiction": "US",
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_same_corpus_produces_same_manifest_hash(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_a = tmp_path / "out-a"
    output_b = tmp_path / "out-b"
    source_dir.mkdir()

    _write_policy(
        source_dir / "policy-b.json",
        doc_id="policy-b",
        content="Retention period is seven years for tax records.",
    )
    _write_policy(
        source_dir / "policy-a.json",
        doc_id="policy-a",
        content="Vendor data sharing needs legal approval and DPA execution.",
    )

    manifest_a, path_a = build_corpus_snapshot(
        source_dir,
        output_a,
        version_tag="week-02-v1",
        chunk_size=80,
        chunk_overlap=10,
    )
    manifest_b, path_b = build_corpus_snapshot(
        source_dir,
        output_b,
        version_tag="week-02-v1",
        chunk_size=80,
        chunk_overlap=10,
    )

    assert manifest_a.manifest_hash == manifest_b.manifest_hash
    assert manifest_a.doc_count == 2
    assert manifest_a.chunk_count == manifest_b.chunk_count
    assert manifest_a.metadata_coverage["doc_id"] == 1.0
    assert path_a.name == "manifest-week-02-v1.json"
    assert path_b.name == "manifest-week-02-v1.json"
    assert path_a.exists()
    assert path_b.exists()

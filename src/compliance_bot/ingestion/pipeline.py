"""Week 2 ingestion pipeline entrypoint."""

from __future__ import annotations

import argparse
from pathlib import Path

from compliance_bot.ingestion.chunker import chunk_corpus
from compliance_bot.ingestion.loaders import load_policy_documents
from compliance_bot.ingestion.manifest_builder import build_manifest, write_manifest
from compliance_bot.ingestion.metadata_validator import build_metadata_coverage_report
from compliance_bot.schemas.ingestion import CorpusManifest


DEFAULT_SOURCE_DIR = Path("docs/policies/sanitized")
DEFAULT_OUTPUT_DIR = Path("artifacts/corpus")


def build_corpus_snapshot(
    source_dir: Path,
    output_dir: Path,
    *,
    version_tag: str,
    chunk_size: int,
    chunk_overlap: int,
) -> tuple[CorpusManifest, Path]:
    """Run the full Week 2 ingestion flow and write a manifest snapshot."""

    documents = load_policy_documents(source_dir)
    metadata_report = build_metadata_coverage_report(documents)
    chunks = chunk_corpus(
        documents,
        version_tag=version_tag,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    manifest = build_manifest(
        chunks,
        version_tag=version_tag,
        metadata_report=metadata_report,
    )
    manifest_path = write_manifest(manifest, output_dir)
    return manifest, manifest_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Week 2 corpus manifest snapshot")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="Folder containing sanitized policy JSON documents",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Folder to write manifest JSON artifact",
    )
    parser.add_argument(
        "--version-tag",
        required=True,
        help="Version tag such as week-02-v1",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=700,
        help="Chunk size in characters",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=120,
        help="Chunk overlap in characters",
    )
    return parser


def main() -> None:
    """CLI entrypoint for Week 2 ingestion."""

    args = _build_parser().parse_args()
    manifest, path = build_corpus_snapshot(
        args.source_dir,
        args.output_dir,
        version_tag=args.version_tag,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    print(f"manifest_path: {path}")
    print(f"manifest_hash: {manifest.manifest_hash}")
    print(f"doc_count: {manifest.doc_count}")
    print(f"chunk_count: {manifest.chunk_count}")


if __name__ == "__main__":
    main()

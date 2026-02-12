"""Week 2 metadata validation for ingestion governance."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Mapping, Sequence

from compliance_bot.schemas.ingestion import LoadedDocument, MetadataCoverageReport

REQUIRED_METADATA_KEYS: tuple[str, ...] = (
    "doc_id",
    "effective_date",
    "owner",
    "jurisdiction",
)
_DOC_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def validate_required_metadata(metadata: Mapping[str, str]) -> None:
    """Validate presence of required metadata keys."""

    missing = sorted(key for key in REQUIRED_METADATA_KEYS if key not in metadata)
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"missing required metadata keys: {joined}")


def validate_document_metadata(document: LoadedDocument) -> None:
    """Validate metadata shape and value formats for a single document."""

    metadata = document.metadata
    validate_required_metadata(metadata)

    doc_id = metadata["doc_id"].strip()
    if not _DOC_ID_PATTERN.match(doc_id):
        raise ValueError(f"invalid doc_id '{doc_id}' in {document.source_path}")

    effective_date = metadata["effective_date"].strip()
    try:
        datetime.strptime(effective_date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(
            f"invalid effective_date '{effective_date}' in {document.source_path}"
        ) from exc

    for key in ("owner", "jurisdiction"):
        if not metadata[key].strip():
            raise ValueError(f"metadata field '{key}' must not be blank")


def build_metadata_coverage_report(
    documents: Sequence[LoadedDocument],
) -> MetadataCoverageReport:
    """Validate corpus metadata and compute required-key coverage."""

    total_documents = len(documents)
    if total_documents == 0:
        return MetadataCoverageReport(
            total_documents=0,
            valid_documents=0,
            coverage_by_key={key: 0.0 for key in REQUIRED_METADATA_KEYS},
        )

    presence_counts = {key: 0 for key in REQUIRED_METADATA_KEYS}
    for document in documents:
        validate_document_metadata(document)
        for key in REQUIRED_METADATA_KEYS:
            if document.metadata[key].strip():
                presence_counts[key] += 1

    coverage = {
        key: round(presence_counts[key] / total_documents, 4)
        for key in REQUIRED_METADATA_KEYS
    }
    return MetadataCoverageReport(
        total_documents=total_documents,
        valid_documents=total_documents,
        coverage_by_key=coverage,
    )

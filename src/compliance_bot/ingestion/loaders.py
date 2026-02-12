"""Week 2 document loaders for sanitized policy corpora."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from compliance_bot.schemas.ingestion import LoadedDocument


def _normalize_metadata(raw_metadata: dict[str, Any]) -> dict[str, str]:
    """Normalize metadata values into trimmed strings."""

    return {str(key): str(value).strip() for key, value in raw_metadata.items()}


def load_policy_documents(source_dir: Path) -> list[LoadedDocument]:
    """Load all approved policy JSON files from a source directory."""

    if not source_dir.exists():
        raise FileNotFoundError(f"source directory does not exist: {source_dir}")

    policy_files = sorted(path for path in source_dir.glob("*.json") if path.is_file())
    if not policy_files:
        raise ValueError(f"no policy JSON files found in {source_dir}")

    documents: list[LoadedDocument] = []
    for path in policy_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"policy file must contain a JSON object: {path}")

        raw_metadata = payload.get("metadata", {})
        if not isinstance(raw_metadata, dict):
            raise ValueError(f"metadata must be a JSON object: {path}")

        content = payload.get("content", "")
        documents.append(
            LoadedDocument(
                content=str(content),
                metadata=_normalize_metadata(raw_metadata),
                source_path=str(path),
            )
        )

    return documents

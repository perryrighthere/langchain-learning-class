"""Week 2 metadata validator tests."""

from __future__ import annotations

import pytest

from compliance_bot.ingestion.metadata_validator import validate_required_metadata


def test_missing_metadata_field_fails_validation() -> None:
    metadata = {
        "doc_id": "expense-policy-v1",
        "owner": "compliance-team",
        "jurisdiction": "US",
    }

    with pytest.raises(ValueError, match="effective_date"):
        validate_required_metadata(metadata)

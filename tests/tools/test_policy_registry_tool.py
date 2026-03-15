"""Tests for the Week 6 policy registry tool."""

from __future__ import annotations

from compliance_bot.retrieval.indexer import build_retrieval_index
from compliance_bot.schemas.ingestion import ChunkRecord, CorpusManifest
from compliance_bot.schemas.tools import PolicyRegistryLookupInput
from compliance_bot.tools.policy_registry_tool import lookup_policy_registry


def _build_index():
    manifest = CorpusManifest(
        version_tag="week-06-v1",
        manifest_hash="a" * 64,
        doc_count=2,
        chunk_count=2,
        metadata_coverage={"doc_id": 1.0, "jurisdiction": 1.0},
        chunks=[
            ChunkRecord(
                chunk_id="chunk-expense-0001",
                doc_id="expense-policy-v1",
                version_tag="week-06-v1",
                chunk_index=0,
                content="Expense reimbursement requires manager approval with receipt evidence.",
                metadata={
                    "jurisdiction": "US",
                    "policy_scope": "expense,reimbursement",
                    "section": "4.2",
                },
            ),
            ChunkRecord(
                chunk_id="chunk-vendor-0001",
                doc_id="vendor-policy-v2",
                version_tag="week-06-v1",
                chunk_index=0,
                content="Vendor onboarding in the EU requires legal review and DPA approval.",
                metadata={
                    "jurisdiction": "EU",
                    "policy_scope": "vendor,privacy",
                    "section": "7.1",
                },
            ),
        ],
    )
    return build_retrieval_index(manifest)


def test_policy_registry_lookup_returns_matching_policy_summary() -> None:
    result = lookup_policy_registry(
        _build_index(),
        PolicyRegistryLookupInput(
            question="Which expense policy section approves reimbursements?",
            jurisdiction="US",
            policy_scope=["expense"],
        ),
    )

    assert result.resolved is True
    assert result.matches
    assert result.matches[0].doc_id == "expense-policy-v1"
    assert "expense-policy-v1@week-06-v1" in result.summary


def test_policy_registry_lookup_returns_unresolved_when_scope_is_missing() -> None:
    result = lookup_policy_registry(
        _build_index(),
        PolicyRegistryLookupInput(
            question="What is the data retention rule?",
            jurisdiction="US",
            policy_scope=["retention"],
        ),
    )

    assert result.resolved is False
    assert result.matches == []

# Week 2 Requirements: Ingestion, Metadata Governance, and Versioning

## Objective
Ship a deterministic ingestion pipeline that validates metadata and produces a reproducible corpus manifest.

## Scope
- Load sanitized policy documents from an approved folder.
- Validate required metadata keys and value formats.
- Chunk documents with stable chunk IDs.
- Build and persist a deterministic versioned manifest snapshot.

## Out of Scope
- Vector indexing and retrieval ranking.
- Citation generation and answer synthesis.
- LangGraph orchestration and audit replay.

## Acceptance Criteria

| ID | Requirement | Verification |
| --- | --- | --- |
| AC-1 | Missing required metadata key fails validation. | Unit test `test_missing_metadata_field_fails_validation` |
| AC-2 | Same corpus + same version tag yields same manifest hash. | Integration test `test_same_corpus_produces_same_manifest_hash` |
| AC-3 | CLI pipeline writes `manifest-<version>.json` with document/chunk counts. | Manual run via `python -m compliance_bot.ingestion.pipeline` |

## Risk Register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Non-deterministic file ordering | Hash drift across runs | Sort input files and chunk records deterministically |
| Metadata drift | Missing accountability fields | Enforce required keys + format checks before chunking |
| Chunking instability | Manifest changes without source changes | Normalize whitespace and stable chunk ID construction |

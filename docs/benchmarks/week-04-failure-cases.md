# Week 4 Failure Examples Catalog

## Case 1: Missing Citation on ANSWERED
- Symptom: model outputs `decision="ANSWERED"` with empty `citations`.
- Expected behavior: output rejected by schema/policy and converted to controlled `ABSTAINED`.

## Case 2: Citation Chunk Mismatch
- Symptom: citation `chunk_id` does not exist in retrieved chunks.
- Expected behavior: `citations_are_grounded(...)` fails, final response becomes `ABSTAINED`.

## Case 3: Version Drift Citation
- Symptom: citation has correct `chunk_id` but wrong `version`.
- Expected behavior: citation validation fails and final response becomes `ABSTAINED`.

## Case 4: Provider Timeout
- Symptom: hosted LLM invocation raises timeout.
- Expected behavior: deterministic `ESCALATE` with `abstention_reason="llm_timeout"` and audit `error_code`.

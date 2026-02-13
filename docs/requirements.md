# Week 1 Requirements: Business Framing and Baseline Chain

## Objective
Ship a baseline compliance Q&A chain that returns a safe, parseable structure without retrieval.

## Scope
- Build an LCEL baseline chain in `src/compliance_bot/chains/baseline_chain.py`.
- Define Week 1 schemas in `src/compliance_bot/schemas/query.py`.
- Ensure abstention behavior when context is missing or insufficient.

## Out of Scope
- Document ingestion and chunking.
- Retrieval and vector index integration.
- Citation objects and validation.
- LangGraph multi-node orchestration.

## Acceptance Criteria

| ID | Requirement | Verification |
| --- | --- | --- |
| AC-1 | Output is always parseable into `BaselineChainOutput` with `answer`, `confidence`, `decision`. | Unit test `test_structured_response_is_parseable` |
| AC-2 | Missing or unknown context leads to `ABSTAINED`. | Unit test `test_unknown_context_triggers_abstained` |
| AC-3 | Baseline chain runs end-to-end via LCEL prompt -> model -> parser pipeline. | Unit tests invoke `build_baseline_chain` + `invoke_baseline_chain` |

## Risk Register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Model emits non-JSON text | Parser failure and inconsistent API behavior | Use explicit format instructions via `PydanticOutputParser` and enforce parser stage |
| Ambiguous abstention rules | Unsafe answers without evidence | Use deterministic sentinel (`NO_CONTEXT_AVAILABLE`) and explicit prompt policy |
| Tight coupling to provider SDK | Harder migration in later weeks | Keep baseline chain model input typed as generic `Runnable` |


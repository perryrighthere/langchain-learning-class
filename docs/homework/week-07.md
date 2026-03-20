# Week 7 Homework

## Objective
Extend the Week 7 guardrail layer so that students can prove access control and sensitive-data protections still hold when the policy matrix or redaction surface grows.

## Estimated Effort
60-120 minutes.

## Implementation Task
1. Add one new Week 7 guardrail case:
   - either introduce one new `user_role` in `src/compliance_bot/guardrails/rbac_filter.py`,
   - or add one new redaction pattern in `src/compliance_bot/guardrails/pii_redactor.py`.
2. Add one workflow-level safety test in `tests/graph/test_workflow.py` covering your change:
   - restricted role stays blocked, or
   - new sensitive pattern is redacted from final state.
3. Keep the implementation inside existing Week 7 modules:
   - `src/compliance_bot/guardrails/rbac_filter.py`
   - `src/compliance_bot/guardrails/injection_detector.py`
   - `src/compliance_bot/guardrails/pii_redactor.py`
   - `src/compliance_bot/graph/workflow.py`

## Verification Task
1. Run Week 7 tests:
   - `.venv/bin/pytest -q tests/guardrails/test_guardrails.py tests/graph/test_workflow.py`
2. Run one normal Week 7 query:
   - `PYTHONPATH=src .venv/bin/python -m compliance_bot.graph.workflow --manifest-path artifacts/corpus/manifest-week-02-v1.json --question "Who approves expense reimbursement requests?" --jurisdiction US --user-role employee --policy-scope expense --embedding-provider none --rerank-provider none --llm-provider none --tool-timeout-ms 5000 --exception-log-path docs/policies/sanitized/exception-log-week-07.json`
3. Run one blocked Week 7 query:
   - `PYTHONPATH=src .venv/bin/python -m compliance_bot.graph.workflow --manifest-path artifacts/corpus/manifest-week-02-v1.json --question "Can I share vendor data with the processor?" --jurisdiction US --user-role employee --policy-scope vendor --embedding-provider none --rerank-provider none --llm-provider none --tool-timeout-ms 5000 --exception-log-path docs/policies/sanitized/exception-log-week-07.json`
4. If SiliconFlow is configured, run one provider-backed Week 7 query:
   - `SILICONFLOW_API_KEY=... SILICONFLOW_EMBEDDING_MODEL=BAAI/bge-m3 SILICONFLOW_RERANK_MODEL=BAAI/bge-reranker-v2-m3 SILICONFLOW_MODEL=Qwen/Qwen3-14B PYTHONPATH=src .venv/bin/python -m compliance_bot.graph.workflow --manifest-path artifacts/corpus/manifest-week-02-v1.json --question "Who approves expense reimbursement requests?" --jurisdiction US --user-role compliance_analyst --policy-scope expense --embedding-provider siliconflow --rerank-provider siliconflow --llm-provider siliconflow --tool-timeout-ms 5000 --exception-log-path docs/policies/sanitized/exception-log-week-07.json`

## Deliverables
- Changed files:
  - one or more files under `src/compliance_bot/guardrails/`
  - one or more files under `tests/guardrails/` or `tests/graph/`
- Command output:
  - Week 7 test command output
  - one normal Week 7 CLI output JSON
  - one blocked Week 7 CLI output JSON
- Short note (4-8 lines):
  - which role was used,
  - whether retrieval was blocked or allowed,
  - which guardrail flags appeared,
  - what fields were redacted,
  - why the final decision was `ANSWERED` or `ESCALATE`.

## Expected Output
- Guardrail behavior remains deterministic and visible in `policy_flags`.
- Restricted queries do not retrieve unauthorized chunks.
- Sensitive patterns are redacted from final workflow output fields.
- Replayable graph stages still include `normalize`, `tool_plan`, `retrieve`, `answer`, `policy_check`, `escalation`, and `finalize`.

## Acceptance Checklist
- [ ] Added one new Week 7 guardrail case.
- [ ] Added one matching test for the new case.
- [ ] Week 7 guardrail and graph tests pass.
- [ ] Produced one normal and one blocked Week 7 CLI run.
- [ ] Confirmed guardrail flags explain the final decision.
- [ ] Confirmed sensitive text is redacted where applicable.

# Week 5 Homework

## Objective
Implement and verify one bounded-retry scenario in the Week 5 LangGraph workflow, then show a concrete output-level difference between normal LangChain and LangGraph.

## Estimated Effort
60-120 minutes.

## Implementation Task
1. Add one integration test in `tests/graph/test_workflow.py`:
   - first answer attempt raises `TimeoutError`,
   - second attempt returns a valid citation-grounded `ANSWERED` payload,
   - `max_answer_retries` is set to `1`.
2. Run or inspect the comparison helper:
   - `python -m compliance_bot.graph.comparison`
   - identify graph-only fields (`decision_path`, `answer_attempt`, replay summary).

## Verification Task
1. Run Week 5 tests:
   - `.venv/bin/pytest -q tests/graph/test_workflow.py tests/audit/test_replay.py tests/graph/test_comparison.py`
2. Run Week 5 workflow CLI in non-provider mode:
   - `PYTHONPATH=src .venv/bin/python -m compliance_bot.graph.workflow --manifest-path artifacts/corpus/manifest-week-02-v1.json --question "Who approves expense reimbursement requests?" --jurisdiction US --policy-scope expense --embedding-provider none --rerank-provider none --llm-provider none --max-answer-retries 1`
3. Save CLI output to JSON, then replay:
   - `PYTHONPATH=src .venv/bin/python -m compliance_bot.audit.replay --response-path artifacts/week5-response.json`
4. Run side-by-side comparison:
   - `PYTHONPATH=src .venv/bin/python -m compliance_bot.graph.comparison --manifest-path artifacts/corpus/manifest-week-02-v1.json --question "Who approves expense reimbursement requests?" --jurisdiction US --policy-scope expense --embedding-provider none --rerank-provider none --llm-provider none --min-confidence-for-answer 0.5`
   - if saving strict JSON output, add `--json-only`.

## Deliverables
- Changed files:
  - `tests/graph/test_workflow.py`
- Command output:
  - Week 5 test command output
  - Week 5 CLI output JSON
  - Week 5 replay CLI output JSON
  - Week 5 comparison CLI output JSON
- Short note (4-8 lines):
  - whether retry executed exactly once,
  - whether replay `decision_path` matched state `decision_path`,
  - which fields are only present in LangGraph output,
  - whether final responses remained citation-safe in both flows.

## Expected Output
- Integration test passes and proves bounded retry behavior.
- Replay summary contains the same path steps as workflow state.
- All audit events in the run share one `trace_id`.
- Final decision does not violate Week 4 citation safety constraints.
- Comparison output explicitly shows LangGraph-only control-flow observability fields.

## Acceptance Checklist
- [ ] Added/updated retry continuity integration test.
- [ ] Week 5 tests pass.
- [ ] Generated replay summary from a saved Week 5 CLI response.
- [ ] Confirmed one-trace audit continuity and citation-safe outcome.
- [ ] Compared normal LangChain and LangGraph outputs with the comparison CLI.

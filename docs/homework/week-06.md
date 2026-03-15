# Week 6 Homework

## Objective
Extend and verify the Week 6 tool-enabled workflow so that students can prove when tool findings should force human review even if retrieval remains strong.

## Estimated Effort
60-120 minutes.

## Implementation Task
1. Add one integration test for a tool-driven escalation scenario:
   - retrieval still finds relevant evidence,
   - `exception_log_lookup` returns at least one open record,
   - final workflow state becomes `ESCALATE`,
   - `requires_human_review` is `true`.
2. Add one real-time tool test:
   - `tavily_search` is selected for a latest/current question,
   - tool arguments are preserved in `state.tool_plan.tool_arguments`,
   - tool execution appears in `state.tool_results`.
3. Keep the implementation inside existing Week 6 modules:
   - `src/compliance_bot/tools/exception_log_tool.py`
   - `src/compliance_bot/tools/tavily_search_tool.py`
   - `src/compliance_bot/graph/workflow.py`
   - `src/compliance_bot/graph/escalation_node.py`

## Verification Task
1. Run Week 6 tests:
   - `.venv/bin/pytest -q tests/tools tests/graph/test_workflow.py tests/audit/test_replay.py`
2. Run Week 6 workflow in normal policy lookup mode:
   - `PYTHONPATH=src .venv/bin/python -m compliance_bot.graph.workflow --manifest-path artifacts/corpus/manifest-week-02-v1.json --question "Which policy section covers expense reimbursement?" --jurisdiction US --policy-scope expense --embedding-provider none --rerank-provider none --llm-provider none --tool-timeout-ms 250 --exception-log-path docs/policies/sanitized/exception-log-week-06.json`
3. Run Week 6 workflow in exception-review mode:
   - `PYTHONPATH=src .venv/bin/python -m compliance_bot.graph.workflow --manifest-path artifacts/corpus/manifest-week-02-v1.json --question "Can we approve a vendor exception override in the EU?" --jurisdiction EU --policy-scope vendor --embedding-provider none --rerank-provider none --llm-provider none --tool-timeout-ms 250 --exception-log-path docs/policies/sanitized/exception-log-week-06.json`
4. If Tavily is configured, run one real-time query:
   - `TAVILY_API_KEY=... PYTHONPATH=src .venv/bin/python -m compliance_bot.graph.workflow --manifest-path artifacts/corpus/manifest-week-02-v1.json --question "What is the latest public guidance on expense reimbursement approvals?" --jurisdiction US --policy-scope expense --embedding-provider siliconflow --rerank-provider siliconflow --llm-provider siliconflow --tool-timeout-ms 250 --exception-log-path docs/policies/sanitized/exception-log-week-06.json`
5. Replay one saved Week 6 response:
   - `PYTHONPATH=src .venv/bin/python -m compliance_bot.audit.replay --response-path artifacts/week6-response.json`

## Deliverables
- Changed files:
  - one or more files under `tests/tools/` or `tests/graph/`
- Command output:
  - Week 6 test command output
  - normal Week 6 CLI output JSON
  - exception-review Week 6 CLI output JSON
  - Week 6 replay output JSON
- Short note (4-8 lines):
  - which tools were planned,
  - whether any tool degraded or stayed unresolved,
  - why the final decision was `ANSWERED` or `ESCALATE`,
  - whether replay matched `state.decision_path`.

## Expected Output
- At least one tool-driven escalation case is covered by tests.
- Workflow output exposes `tool_plan`, `tool_results`, `requires_human_review`, and `escalation_reason`.
- If Tavily is configured, workflow output also exposes real-time search context in `tool_context`.
- Replay summary includes `tool_plan`, `tools`, and `escalation` in the reconstructed path.
- Normal in-scope policy queries can still complete with citation-grounded `ANSWERED`.

## Acceptance Checklist
- [ ] Added one Week 6 tool/escalation test.
- [ ] Added or exercised one Tavily real-time tool test/path.
- [ ] Week 6 tool and graph tests pass.
- [ ] Produced one normal and one escalated Week 6 CLI run.
- [ ] Verified replay path matches workflow state.
- [ ] Confirmed citation-safe answers still work for non-escalated runs.

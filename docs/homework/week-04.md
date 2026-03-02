# Week 4 Homework

## Objective
Implement one additional grounding safety test and compare Week 4 output behavior between `none` and `siliconflow` LLM provider modes.

## Estimated Effort
60-120 minutes.

## Implementation Task
1. Add one test in `tests/chains/test_citation_chain.py` for quote-span mismatch:
   - model returns `ANSWERED` with a citation whose `quote_span` does not appear in the cited chunk content,
   - final response must be `ABSTAINED`.

## Verification Task
1. Run Week 4 chain tests:
   - `.venv/bin/pytest -q tests/chains/test_citation_chain.py`
2. Run Week 4 CLI in non-provider mode:
   - `PYTHONPATH=src .venv/bin/python -m compliance_bot.chains.citation_chain --manifest-path artifacts/corpus/manifest-week-02-v1.json --question "Who approves expense reimbursement requests?" --jurisdiction US --policy-scope expense --embedding-provider none --rerank-provider none --llm-provider none`
3. Run Week 4 CLI in SiliconFlow mode (if key available):
   - `PYTHONPATH=src .venv/bin/python -m compliance_bot.chains.citation_chain --manifest-path artifacts/corpus/manifest-week-02-v1.json --question "Who approves expense reimbursement requests?" --jurisdiction US --policy-scope expense --embedding-provider siliconflow --rerank-provider siliconflow --llm-provider siliconflow`

## Deliverables
- Changed files:
  - `tests/chains/test_citation_chain.py`
- Command output:
  - Week 4 test command output
  - Week 4 CLI output in `none` mode
  - Week 4 CLI output in `siliconflow` mode (or short note that key is unavailable)
- Short note (3-6 lines):
  - which fields changed across the two modes,
  - whether both modes stayed citation-safe.

## Expected Output
- New test fails before the fix and passes after the fix.
- Final test run passes with no failures.
- CLI output remains safe:
  - no uncited `ANSWERED` response,
  - invalid citations never pass final grounding checks.

## Acceptance Checklist
- [ ] Added quote-span mismatch safety test.
- [ ] Week 4 tests pass.
- [ ] Compared `none` and `siliconflow` outputs using actual command output.
- [ ] Confirmed citation safety in both modes.

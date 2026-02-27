# Week 3 Homework

## Objective
Increase benchmark difficulty and compare retrieval performance between SiliconFlow provider mode and non-provider fallback mode.

## Estimated Effort
60-120 minutes.

## Implementation Task
1. Add one challenging benchmark case (paraphrase or multi-policy expectation) to a case file under `docs/benchmarks/`.
2. If needed, tune retrieval config (`top_k` or threshold) for better precision/recall tradeoff.

## Verification Task
1. Run retrieval/provider tests to confirm fallback behavior remains stable.
2. Run benchmark in `none` mode.
3. Run benchmark in `siliconflow` mode (if API key available).
4. Keep one run at strict profile (`top_k=1`) and analyze recall impact.

## Deliverables
- Changed files:
  - benchmark case JSON under `docs/benchmarks/`.
  - optional retrieval/provider module updates.
- Command output:
  - `.venv/bin/pytest -q tests/retrieval tests/providers`
  - `PYTHONPATH=src .venv/bin/python -m compliance_bot.retrieval.benchmarks --manifest-path <manifest_path> --cases-path <cases_path> --embedding-provider none --rerank-provider none`
  - `PYTHONPATH=src .venv/bin/python -m compliance_bot.retrieval.benchmarks --manifest-path <manifest_path> --cases-path <cases_path> --embedding-provider siliconflow --rerank-provider siliconflow`

## Expected Output
- Retrieval/provider tests pass with no failures.
- Benchmark output clearly shows:
  - selected provider mode,
  - resolved backend (`lexical-only`/`none` or `siliconflow:<model>`),
  - recall/latency quality metrics.

## Acceptance Checklist
- [ ] At least one benchmark case is not a direct lexical match.
- [ ] At least one benchmark case expects multiple policy docs.
- [ ] Non-provider mode (`none`) still returns safe deterministic results.
- [ ] If provider mode is used, output includes resolved SiliconFlow backend identifiers.

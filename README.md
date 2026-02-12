# LangChain Compliance Bot

Week 1-2 implementation of a compliance Q&A foundation:
- Week 1: baseline LCEL chain with structured output.
- Week 2: deterministic ingestion pipeline with metadata governance and corpus manifest versioning.

## Code Structure

- `src/compliance_bot/schemas/query.py`: Week 1 input/output schemas and `DecisionEnum`.
- `src/compliance_bot/schemas/ingestion.py`: Week 2 schemas for loaded docs, chunks, and corpus manifests.
- `src/compliance_bot/chains/baseline_chain.py`: Baseline prompt + model + structured parser pipeline.
- `src/compliance_bot/ingestion/loaders.py`: Loads sanitized policy JSON files from a source folder.
- `src/compliance_bot/ingestion/metadata_validator.py`: Validates required metadata and produces coverage report.
- `src/compliance_bot/ingestion/chunker.py`: Deterministic chunking with stable chunk IDs.
- `src/compliance_bot/ingestion/manifest_builder.py`: Deterministic manifest hash + JSON artifact writer.
- `src/compliance_bot/ingestion/pipeline.py`: Week 2 CLI pipeline entrypoint.
- `src/compliance_bot/llms/siliconflow.py`: SiliconFlow provider adapter and environment-based config loader.
- `src/compliance_bot/main.py`: CLI entrypoint wired to baseline chain + SiliconFlow provider.
- `docs/requirements.md`: Week 1 scope, acceptance criteria, and risk register.
- `docs/week-02-requirements.md`: Week 2 scope, acceptance criteria, and risk register.
- `docs/homework/week-02.md`: Week 2 homework brief and acceptance checklist.
- `tests/chains/test_baseline_chain.py`: Parseability and abstention behavior tests.
- `tests/ingestion/test_metadata_validator.py`: Week 2 metadata validation tests.
- `tests/ingestion/test_manifest_builder.py`: Week 2 deterministic manifest integration test.
- `tests/llms/test_siliconflow.py`: SiliconFlow config and provider construction tests.
- `tests/conftest.py`: Adds `src/` to Python path for test imports.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run Tests

```bash
pytest -q
```

## Run Week 2 Ingestion Pipeline

Input policy files should be JSON objects with this shape:

```json
{
  "content": "Policy text...",
  "metadata": {
    "doc_id": "expense-policy-v1",
    "effective_date": "2026-02-01",
    "owner": "compliance-team",
    "jurisdiction": "US"
  }
}
```

Run:

```bash
PYTHONPATH=src python -m compliance_bot.ingestion.pipeline \
  --source-dir docs/policies/sanitized \
  --output-dir artifacts/corpus \
  --version-tag week-02-v1
```

## Run CLI Homework

```bash
export SILICONFLOW_API_KEY="your-api-key"
# Optional:
# export SILICONFLOW_MODEL="Qwen/Qwen3-14B"
# export SILICONFLOW_BASE_URL="https://api.siliconflow.cn/v1"
PYTHONPATH=src python -m compliance_bot.main
```

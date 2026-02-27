# LangChain Compliance Bot

Week 1-3 implementation of a compliance Q&A foundation:
- Week 1: baseline LCEL chain with structured output.
- Week 2: deterministic ingestion pipeline with metadata governance and corpus manifest versioning.
- Week 3: practical provider-backed retrieval foundation (SiliconFlow-first embedding/rerank) with safe fallback, decisions, and benchmark gates.

## Code Structure

- `src/compliance_bot/schemas/query.py`: Week 1 input/output schemas and `DecisionEnum`.
- `src/compliance_bot/schemas/audit.py`: Audit event schema and deterministic hash-based event builder.
- `src/compliance_bot/schemas/ingestion.py`: Week 2 schemas for loaded docs, chunks, and corpus manifests.
- `src/compliance_bot/schemas/retrieval.py`: Week 3 schemas for filters, query rewrite output, citations, retrieval responses, and benchmark reports.
- `src/compliance_bot/chains/baseline_chain.py`: Baseline prompt + model + structured parser pipeline.
- `src/compliance_bot/ingestion/loaders.py`: Loads sanitized policy JSON files from a source folder.
- `src/compliance_bot/ingestion/metadata_validator.py`: Validates required metadata and produces coverage report.
- `src/compliance_bot/ingestion/chunker.py`: Deterministic chunking with stable chunk IDs.
- `src/compliance_bot/ingestion/manifest_builder.py`: Deterministic manifest hash + JSON artifact writer.
- `src/compliance_bot/ingestion/pipeline.py`: Week 2 CLI pipeline entrypoint.
- `src/compliance_bot/retrieval/indexer.py`: Builds in-memory retrieval index from Week 2 manifest files.
- `src/compliance_bot/retrieval/query_rewriter.py`: LCEL query rewriting chain and deterministic fallback.
- `src/compliance_bot/retrieval/retriever.py`: Metadata-aware retriever with provider-backed scoring/rerank and safe fallback.
- `src/compliance_bot/retrieval/benchmarks.py`: Recall/latency benchmark runner with provider mode flags.
- `src/compliance_bot/providers/siliconflow_embeddings.py`: SiliconFlow embedding adapter and typed config loader.
- `src/compliance_bot/providers/siliconflow_rerank.py`: SiliconFlow rerank adapter and safe error mapping.
- `src/compliance_bot/providers/provider_registry.py`: Provider mode resolver (`auto`, `none`, `siliconflow`).
- `src/compliance_bot/llms/siliconflow.py`: SiliconFlow provider adapter and environment-based config loader.
- `src/compliance_bot/main.py`: CLI entrypoint wired to baseline chain + SiliconFlow provider.
- `docs/requirements.md`: Week 1 scope, acceptance criteria, and risk register.
- `docs/week-02-requirements.md`: Week 2 scope, acceptance criteria, and risk register.
- `docs/week-03-requirements.md`: Week 3 scope, acceptance criteria, and risk register.
- `docs/benchmarks/week-03-cases.example.json`: Example retrieval benchmark case file.
- `docs/homework/week-02.md`: Week 2 homework brief and acceptance checklist.
- `docs/homework/week-03.md`: Week 3 homework brief and acceptance checklist.
- `docs/teaching-scripts/week-02.md`: Week 2 teaching script.
- `docs/teaching-scripts/week-03.md`: Week 3 teaching script.
- `tests/chains/test_baseline_chain.py`: Parseability and abstention behavior tests.
- `tests/ingestion/test_metadata_validator.py`: Week 2 metadata validation tests.
- `tests/ingestion/test_manifest_builder.py`: Week 2 deterministic manifest integration test.
- `tests/retrieval/test_query_rewriter.py`: Structured query rewrite parseability and fallback behavior tests.
- `tests/retrieval/test_retriever.py`: Metadata filter, provider fallback, decision path, citation linkage, and audit event tests.
- `tests/retrieval/test_indexer.py`: Provider embedding index build tests.
- `tests/retrieval/test_benchmarks.py`: Recall and quality gate benchmark tests.
- `tests/providers/test_siliconflow_embeddings.py`: SiliconFlow embedding adapter config and construction tests.
- `tests/providers/test_siliconflow_rerank.py`: SiliconFlow rerank response mapping and timeout handling tests.
- `tests/providers/test_provider_registry.py`: Provider mode resolution tests.
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
.venv/bin/pytest -q
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
PYTHONPATH=src .venv/bin/python -m compliance_bot.ingestion.pipeline \
  --source-dir docs/policies/sanitized \
  --output-dir artifacts/corpus \
  --version-tag week-02-v1
```

## Run Week 3 Retrieval Benchmarks

Use a Week 2 manifest and a benchmark case file.

```bash
PYTHONPATH=src .venv/bin/python -m compliance_bot.retrieval.benchmarks \
  --manifest-path artifacts/corpus/manifest-week-02-v1.json \
  --cases-path docs/benchmarks/week-03-cases.example.json \
  --embedding-provider none \
  --rerank-provider none
```

Default benchmark profile is stricter (`top_k=1`, `recall_floor=0.75`) to avoid inflated recall on small corpora.

To force SiliconFlow provider mode:

```bash
export SILICONFLOW_API_KEY="your-api-key"
export SILICONFLOW_EMBEDDING_MODEL="BAAI/bge-m3"
export SILICONFLOW_RERANK_MODEL="BAAI/bge-reranker-v2-m3"
PYTHONPATH=src .venv/bin/python -m compliance_bot.retrieval.benchmarks \
  --manifest-path artifacts/corpus/manifest-week-02-v1.json \
  --cases-path docs/benchmarks/week-03-cases.example.json \
  --embedding-provider siliconflow \
  --rerank-provider siliconflow \
  --top-k 1 \
  --recall-floor 0.75
```

## Run CLI Homework

```bash
export SILICONFLOW_API_KEY="your-api-key"
# Optional:
# export SILICONFLOW_MODEL="Qwen/Qwen3-14B"
# export SILICONFLOW_BASE_URL="https://api.siliconflow.cn/v1"
PYTHONPATH=src python -m compliance_bot.main
```

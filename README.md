# LangChain Compliance Bot

Week 1 implementation of a compliance Q&A baseline chain using LCEL and structured output parsing.

## Code Structure

- `src/compliance_bot/schemas/query.py`: Week 1 input/output schemas and `DecisionEnum`.
- `src/compliance_bot/chains/baseline_chain.py`: Baseline prompt + model + structured parser pipeline.
- `docs/requirements.md`: Week 1 scope, acceptance criteria, and risk register.
- `tests/chains/test_baseline_chain.py`: Parseability and abstention behavior tests.
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

# Sanitized Class Demo Policies

These dummy policy files are designed to complement Week 3 retrieval benchmarks.

## Included Files
- `expense-policy-v1.json`
- `vendor-policy-v2.json`
- `records-retention-policy-v1.json`

## Regenerate Manifest

```bash
PYTHONPATH=src .venv/bin/python -m compliance_bot.ingestion.pipeline \
  --source-dir docs/policies/sanitized \
  --output-dir artifacts/corpus \
  --version-tag week-02-v1
```

The generated file used by Week 3 benchmark CLI is:
- `artifacts/corpus/manifest-week-02-v1.json`

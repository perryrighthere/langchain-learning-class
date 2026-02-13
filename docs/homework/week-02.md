# Week 2 Homework

## Objective
Implement and verify a deterministic ingestion snapshot for sanitized compliance policies.

## Estimated Effort
60-120 minutes.

## Implementation Task
Add one new sanitized policy JSON document under your own local practice folder and run the Week 2 ingestion pipeline to generate an updated manifest.

## Verification Task
Run tests for Week 2 ingestion and confirm manifest hash stability across two repeated runs with the same corpus and version tag.

## Deliverables
- Changed files: your policy JSON input file and the generated `manifest-<version>.json` artifact.
- Command output:
  - `pytest -q tests/ingestion`
  - `PYTHONPATH=src python -m compliance_bot.ingestion.pipeline --source-dir <your_policy_dir> --output-dir <your_output_dir> --version-tag week-02-v1`

## Expected Output
- Tests pass with no failures.
- Pipeline prints `manifest_path`, `manifest_hash`, `doc_count`, and `chunk_count`.
- Re-running the same command with unchanged inputs yields the same `manifest_hash`.

## Acceptance Checklist
- [ ] Every policy JSON includes `doc_id`, `effective_date`, `owner`, `jurisdiction`.
- [ ] `effective_date` uses `YYYY-MM-DD` format.
- [ ] Manifest file is generated under the specified output folder.
- [ ] Manifest hash is stable across repeated runs with identical input.

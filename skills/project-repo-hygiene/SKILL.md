---
name: project-repo-hygiene
description: Keep repository hygiene aligned with code changes in this project. Use whenever files are added, removed, or refactored to keep README run guidance, dependency declarations, and ignore rules accurate and minimal.
---

# Project Repo Hygiene

## Mandatory Checks Per Code Change

1. Update `README.md` to reflect current code structure and run instructions.
2. Keep README implementation-focused only; exclude teaching plans and curriculum content.
3. Update `requirements.txt` for newly required runtime or test dependencies.
4. Remove unused dependencies from `requirements.txt` when practical.
5. Update `.gitignore` for generated files, caches, local datasets, and secrets.
6. When weekly teaching output is requested, store teaching scripts in `docs/teaching-scripts/week-XX.md`.
7. When weekly teaching output is requested, store homework in `docs/homework/week-XX.md`.

## README Scope Guardrail

1. Include only:
   - module/folder layout,
   - setup commands,
   - run/test commands.
2. Exclude:
   - weekly teaching plan content,
   - assignment text,
   - grading rubrics.

## Teaching Artifact Placement

1. Keep homework and assignment text out of `README.md`.
2. Place weekly teaching scripts under `docs/teaching-scripts/` with week-scoped filenames.
3. Place weekly homework content under `docs/homework/` with week-scoped filenames.
4. If needed, README may link to teaching artifact folders but must not inline curriculum details.

## Dependency Hygiene

1. Keep dependency list concise and purpose-driven.
2. Prefer compatible version ranges.
3. Ensure listed packages match actual imports and tooling.

## Completion Check

1. Confirm documentation, dependencies, and ignore rules are consistent with changed code.
2. Report what was updated and why.

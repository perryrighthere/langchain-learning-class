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

## README Scope Guardrail

1. Include only:
   - module/folder layout,
   - setup commands,
   - run/test commands.
2. Exclude:
   - weekly teaching plan content,
   - assignment text,
   - grading rubrics.

## Dependency Hygiene

1. Keep dependency list concise and purpose-driven.
2. Prefer compatible version ranges.
3. Ensure listed packages match actual imports and tooling.

## Completion Check

1. Confirm documentation, dependencies, and ignore rules are consistent with changed code.
2. Report what was updated and why.


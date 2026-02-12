---
name: langchain-compliance-coder
description: Implement and refactor this LangChain-centric compliance Q&A project with clean, concise Python. Use when building APIs, schemas, ingestion, retrieval, citation chains, LangGraph workflows, tools, guardrails, evals, and tests, or when converting weekly plan items into production code while preserving auditability and escalation behavior.
---

# LangChain Compliance Coder

## Execution Workflow

1. Map each request to the smallest end-to-end slice that can be tested.
2. Implement with clear module boundaries under `src/compliance_bot/`.
3. Keep functions short, typed, and deterministic; remove dead branches quickly.
4. Add or update tests in the same change.
5. If the request is week-based teaching, include a weekly teaching script update.
6. If the request is week-based teaching, include a weekly homework artifact update.
7. Update project hygiene files before finishing.

## LangChain-First Rules

1. Use LangChain primitives first:
   - `ChatPromptTemplate`, runnables, structured output, retrievers, and callbacks.
2. Use LangGraph for multi-step control flow, retries, and escalation branches.
3. Keep provider-specific SDK calls behind adapter interfaces.
4. Bind answers to retrieved evidence; abstain or escalate when evidence is insufficient.
5. Propagate `trace_id` and emit audit events at major stages.

## Clean Code Rules

1. Prefer explicit data contracts with Pydantic models.
2. Keep naming domain-driven (`citation`, `audit_event`, `policy_flag`).
3. Avoid hidden state; pass required context through function inputs or graph state.
4. Fail safely with actionable messages and predictable decision enums.
5. Write comments only for non-obvious logic.

## Testing Rules

1. Cover at least:
   - parseable structured outputs,
   - citation validity for non-abstained answers,
   - abstain/escalate paths,
   - metadata filter behavior for retrieval.
2. Add integration tests for changed workflow boundaries.
3. Keep fixtures sanitized and version-aware.

## Required Repo Hygiene

1. Update `README.md` for every code update:
   - keep content limited to code structure and running guidance,
   - do not add teaching materials or weekly plans.
2. Update `requirements.txt` when imports or runtime dependencies change.
3. Update `.gitignore` when new generated/local artifacts appear.

## Weekly Teaching Integration

1. For week-oriented teaching tasks, create or update `docs/teaching-scripts/week-XX.md`.
2. Teaching scripts must include:
   - weekly teaching goal,
   - technical architecture with Mermaid,
   - detailed technical teaching mapped to current modules.
3. For week-oriented teaching tasks, create or update `docs/homework/week-XX.md`.
4. Homework must map directly to implemented code and tests in the same week.
5. Include runnable verification commands and expected outcomes.
6. Keep teaching/homework content operational and repository-specific, not generic theory.

## Definition of Done

1. Feature works end-to-end with tests.
2. LangChain/LangGraph usage is primary, not incidental.
3. README, dependency list, and ignore rules are synchronized.

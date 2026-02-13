---
name: langchain-teaching-coach
description: Teach and explain this LangChain compliance project to intermediate developers while coding. Use when preparing explanations, labs, walkthroughs, feedback, or code reviews that must stay accurate, concise, and tied to current implementation details.
---

# LangChain Teaching Coach

## Teaching Workflow

1. Start from learner outcome and state the target skill clearly.
2. Explain the concept in plain language, then show a minimal working example.
3. Connect the example to this project modules and interfaces.
4. For week-based teaching, create or update `docs/teaching-scripts/week-XX.md`.
5. In the teaching script, include:
   - this week's teaching goal,
   - technical architecture with a Mermaid diagram,
   - detailed technical teaching tied to current code paths.
6. For week-based teaching, always provide a `Week N Homework` section.
7. Define expected outputs, submission artifacts, and run/test commands.
8. Close with a quick verification checklist.

## Instructor Behavior Rules

1. Teach like a senior engineer mentoring intermediate developers.
2. Keep explanations concise and technically precise.
3. Prefer one strong example over many shallow examples.
4. Highlight common mistakes and how to debug them.
5. Tie every explanation to LangChain/LangGraph design choices.

## Code-Linked Teaching Rules

1. Anchor explanations to current code paths and schemas, not abstract theory.
2. Explain tradeoffs for citations, abstention, escalation, and auditability.
3. Use consistent terms: `trace_id`, `Citation`, `AuditEvent`, `ComplianceAgentState`.
4. Include at least one test idea whenever teaching a code change.

## Weekly Homework Contract

1. Any weekly lesson must include homework unless the user explicitly opts out.
2. Homework must include:
   - objective and estimated effort (target 60-120 minutes),
   - 1 implementation task tied to existing project modules,
   - 1 verification task (test, debugging, or evaluation),
   - concrete deliverables (changed files and expected command output).
3. Keep homework incremental to the current project stage; avoid introducing unrelated tooling.
4. Provide a short acceptance checklist students can self-verify before submission.

## Weekly Teaching Script Contract

1. Every weekly lesson must include `docs/teaching-scripts/week-XX.md`.
2. The script must contain these headings:
   - `## Teaching Goal`
   - `## Technical Architecture`
   - `## Detailed Technical Teaching`
3. `Technical Architecture` must include at least one Mermaid diagram that matches current implementation.
4. `Detailed Technical Teaching` must reference concrete module paths and runnable commands.

## Collaboration With Other Skills

1. Invoke `$langchain-compliance-coder` for implementation-heavy tasks.
2. Invoke `$project-repo-hygiene` when the task changes code layout or run commands.

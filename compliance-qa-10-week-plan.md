# 10-Week Curriculum Plan: Compliance Q&A Bot with Citation and Audit Trail (LangChain-Centric)

## Summary
This plan trains intermediate LLM developers to design, build, evaluate, and operate an enterprise-grade compliance Q&A bot in realistic internal-policy environments.  
The course is structured as weekly delivery cycles (3-4 hours teaching + lab), and every week produces a production-like artifact that feeds a final capstone system.  
The implementation is centered on LangChain + LangGraph, with provider-agnostic model adapters, citation-first answer generation, and auditable execution traces.

## Output Artifact (for implementation step)
Create one markdown file at:
`/Users/perryhe/Projects/langchain-learning/compliance-qa-10-week-plan.md`

The file should contain the full curriculum exactly as specified below, with weekly sections, rubrics, API contracts, and acceptance tests.

## Public APIs / Interfaces / Types Students Will Build
1. `POST /v1/compliance/query`
   Request type: `ComplianceQueryRequest` with `question`, `user_id`, `role`, `jurisdiction`, `policy_scope`, `session_id`.
   Response type: `ComplianceQueryResponse` with `answer`, `citations[]`, `confidence`, `decision`, `trace_id`, `requires_human_review`.
2. `POST /v1/compliance/feedback`
   Request type: `FeedbackRequest` with `trace_id`, `rating`, `issue_type`, `comment`.
   Response type: `FeedbackAck`.
3. `GET /v1/compliance/audit/{trace_id}`
   Response type: `AuditRecord` with prompt chain, retrieval events, tool calls, model metadata, policy checks, final decision rationale.
4. `POST /v1/compliance/documents/reindex`
   Request type: `ReindexRequest` with `source_id`, `version_tag`, `change_reason`.
   Response type: `ReindexStatus`.
5. LangGraph state interface: `ComplianceAgentState`
   Required fields: `question`, `normalized_query`, `retrieved_chunks`, `citations`, `policy_flags`, `decision_path`, `final_answer`, `audit_events`.
6. Citation schema: `Citation` with `doc_id`, `section`, `chunk_id`, `quote_span`, `retrieval_score`, `version`.
7. Audit event schema: `AuditEvent` with `event_id`, `trace_id`, `stage`, `timestamp`, `input_hash`, `output_hash`, `actor`, `status`.

## Weekly Plan (10 Weeks, Detailed)

### Week 1: Business Framing and Compliance Assistant Blueprint
1. Learning goal: translate compliance operations pain points into assistant requirements and measurable risk controls.
2. Real-life scenario: Legal/Compliance team receives high-volume policy questions from internal teams with strict citation and accountability demands.
3. Teaching materials: system context map, stakeholder matrix, compliance query taxonomy, failure-cost analysis template.
4. LangChain focus: architecture overview, LCEL basics, chain decomposition, prompt contracts for compliance tasks.
5. Lab: implement a baseline question-to-answer chain with structured output (no retrieval yet), add explicit “insufficient evidence” branch.
6. Deliverable: `requirements.md`, initial chain notebook/script, risk register v1, acceptance criteria draft.
7. Rubric: clarity of scope, realism of constraints, traceability from requirement to technical design.

### Week 2: Data Ingestion, Document Governance, and Corpus Versioning
1. Learning goal: build ingestion workflows for sanitized policy corpora with versioning and metadata discipline.
2. Real-life scenario: policy updates occur monthly; old answers must remain auditable against historical document versions.
3. Teaching materials: document lifecycle guide, metadata spec (`doc_id`, `effective_date`, `owner`, `jurisdiction`), redaction checklist.
4. LangChain focus: document loaders, text splitters, metadata propagation pipelines.
5. Lab: ingest synthetic/sanitized policies, enforce metadata validation, create reproducible corpus snapshot.
6. Deliverable: ingestion pipeline script, metadata validator, corpus manifest with version tags.
7. Rubric: ingestion correctness, metadata completeness, reproducibility.

### Week 3: Retrieval Foundation for Compliance Q&A
1. Learning goal: produce high-recall, policy-bounded retrieval for compliance queries.
2. Real-life scenario: similar policy language across departments causes ambiguous retrieval and wrong policy grounding.
3. Teaching materials: retrieval quality framework, chunking strategy decision matrix, query-intent normalization examples.
4. LangChain focus: embeddings, vector store integration, retrievers, `MultiQueryRetriever` and contextual query rewriting.
5. Lab: implement retrieval v1, compare chunking and top-k strategies, instrument retrieval metrics.
6. Deliverable: retriever module, benchmark report (recall@k, MRR-like proxy, latency), retriever config registry.
7. Rubric: measured retrieval quality, defensible parameter choices, latency-awareness.

### Week 4: Citation-First Answer Generation and Grounding Controls
1. Learning goal: force answer generation to be evidence-bound with explicit citation objects.
2. Real-life scenario: compliance users reject uncited answers; legal requires exact evidence spans.
3. Teaching materials: citation policy, grounded answer template, abstention logic examples.
4. LangChain focus: retrieval-augmented chains, structured output parsers, context-window control.
5. Lab: build answer chain that only answers from retrieved evidence; if confidence low, return controlled abstention.
6. Deliverable: citation-enforced answer module, citation schema tests, failure examples catalog.
7. Rubric: citation precision, hallucination suppression, abstention quality.

### Week 5: Audit Trail by Design with LangGraph State Machines
1. Learning goal: create deterministic workflow state and event logs for post-hoc audit.
2. Real-life scenario: internal audit requests exact reconstruction of how an answer was generated.
3. Teaching materials: auditable workflow patterns, event sourcing primer, trace reconstruction worksheet.
4. LangChain/LangGraph focus: graph nodes/edges, state persistence, branching, retry and error paths.
5. Lab: refactor chain into LangGraph flow with stage-level events and `trace_id` propagation.
6. Deliverable: graph spec diagram, `ComplianceAgentState` model, `AuditEvent` emitter, audit replay script.
7. Rubric: completeness of event trace, deterministic behavior under reruns, recovery handling.

### Week 6: Tooling, Policy Lookup, and Human Escalation
1. Learning goal: integrate safe tools and escalation logic for unresolved or high-risk queries.
2. Real-life scenario: questions require querying policy registries, exception logs, or contacting compliance analysts.
3. Teaching materials: tool contract patterns, escalation policy matrix, role-based decision paths.
4. LangChain focus: tool calling, router patterns, agent constraints, timeout/fallback handling.
5. Lab: add policy lookup tool and escalation node that triggers human-review flags.
6. Deliverable: tool adapters, escalation rules engine, escalation event logs with rationale.
7. Rubric: safe tool usage, correct escalation triggers, transparent decision rationales.

### Week 7: Guardrails, Access Control, and Sensitive-Data Handling
1. Learning goal: enforce policy and privacy constraints across prompts, retrieval, and responses.
2. Real-life scenario: users with different roles must not receive the same compliance details.
3. Teaching materials: RBAC policy examples, sensitive-content policy, prompt-injection threat model.
4. LangChain focus: middleware/guardrail hooks, input/output filtering, runnable wrappers.
5. Lab: implement role-aware retrieval filters, PII redaction checks, prompt-injection mitigations.
6. Deliverable: guardrail module, adversarial test set, blocked-query behavior report.
7. Rubric: policy enforcement correctness, security resilience, false-positive/false-negative balance.

### Week 8: Evaluation, Red Teaming, and Quality Gates
1. Learning goal: establish objective quality gates for compliance readiness.
2. Real-life scenario: release approval requires measurable standards for faithfulness, citation validity, and risk control.
3. Teaching materials: eval dataset design guide, rubric for compliance answer quality, red-team scenario catalog.
4. LangChain focus: LangSmith traces/evals, dataset-driven evaluation loops, experiment tracking.
5. Lab: run automated eval suite and manual adjudication; tune retrieval and prompts based on errors.
6. Deliverable: eval dashboard snapshot, quality-gate thresholds, remediation backlog.
7. Rubric: metric quality, diagnosis depth, quality-gate rigor.

### Week 9: Production API, Observability, and Operations Readiness
1. Learning goal: package the assistant as an internal API with operational controls.
2. Real-life scenario: platform team needs authenticated service, SLA monitoring, and incident diagnostics.
3. Teaching materials: API contract guide, observability checklist, SLO/SLA template.
4. LangChain focus: production invocation patterns, callback handlers, trace correlation with app logs.
5. Lab: expose `/v1/compliance/query` and `/v1/compliance/audit/{trace_id}` via FastAPI, add auth and telemetry.
6. Deliverable: running internal API service, runbook draft, operational dashboard spec.
7. Rubric: API correctness, observability coverage, deployability.

### Week 10: Capstone Delivery, Incident Drill, and Executive Readout
1. Learning goal: demonstrate end-to-end system performance in a realistic compliance operations simulation.
2. Real-life scenario: multi-department rollout with policy updates, adversarial queries, and audit review requests.
3. Teaching materials: capstone scenario packet, incident drill script, executive briefing template.
4. LangChain/LangGraph focus: full-system orchestration hardening, regression control, post-incident analysis loops.
5. Lab: run live simulation, handle incident ticket, produce audit packet and improvement plan.
6. Deliverable: final demo, architecture dossier, audit evidence bundle, postmortem with prioritized roadmap.
7. Rubric: end-to-end reliability, auditability, stakeholder communication quality, technical depth.

## Weekly Teaching Package Template (applies to every week)
1. Instructor deck with architecture diagrams and failure analysis.
2. Guided lab notebook and equivalent Python module implementation.
3. Student assignment brief with acceptance checklist.
4. Grading rubric with objective criteria and evidence requirements.
5. “Common failure modes” sheet and remediation hints.
6. Optional advanced extension task for stronger students.

## Test Cases and Scenarios (Course-Level Acceptance)
1. Citation integrity test: every non-abstained answer must include at least one valid citation linked to corpus version.
2. Faithfulness test: answer claims must be traceable to retrieved evidence spans.
3. Access-control test: role-restricted users cannot retrieve unauthorized policy content.
4. Policy-update regression test: after reindex, new answers use latest version while old traces remain reproducible.
5. Escalation correctness test: high-risk intents trigger human review with reason code.
6. Prompt-injection resilience test: malicious instructions do not override system policy.
7. Audit replay test: given `trace_id`, pipeline stages can be reconstructed without missing events.
8. Latency budget test: normal queries meet service-level target with bounded variance.
9. Failure-handling test: tool timeout and retriever miss paths return safe, actionable responses.
10. End-to-end drill: simulated quarterly audit passes with complete evidence packet.

## Assumptions and Defaults Chosen
1. Audience: intermediate LLM developers with strong Python fundamentals.
2. Cadence: 3-4 hours/week teaching plus lab and independent assignment.
3. Domain: regulated enterprise internal-policy Q&A (cross-framework style).
4. Tech stack: Python, LangChain + LangGraph hybrid, provider-agnostic model adapters.
5. Data: synthetic + sanitized policy corpus with strict metadata and versioning.
6. Observability: LangSmith plus custom compliance metrics.
7. Deployment target: internal FastAPI service with authentication and audit endpoints.
8. Grading model: weekly artifact rubric plus capstone performance.
9. Language for all teaching artifacts: English.
10. Target markdown filename: `compliance-qa-10-week-plan.md`.

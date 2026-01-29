# RFC 0002: Decision Events, Prompt/Response Provenance, and Comparison Hooks  
## Prototype-First Instrumentation for Agentic Coding

**Status:** Draft (Prototype)  
**Type:** Foundational / Enabling  
**Audience:** Senior engineers, SREs, architects, AI system designers  
**Scope:** Agentic systems that execute work autonomously (coding agents, workflow agents, tool-using LLMs)

---

## 0. Context (Why this RFC exists)

This project aims to make **autonomous agents** (e.g., coding agents) observable in a way that is **actionable** during prototyping:

- You want to run a coding agent **without manual approval**.
- You want to **observe** what it did, why it did it, and whether it stayed aligned with the user's request.
- You want machine-usable outputs (e.g., **JSON**) that can drive dashboards, alerts, gating, postmortems.

This RFC defines the **minimum viable, non-fuzzy** instrumentation required to:
1) capture what the user asked,
2) capture what the agent actually prompted the model with,
3) capture what the model produced and what tools/actions were executed,
4) provide standardized comparison hooks (alignment checks),
5) enable incident review and future SLOs.

This RFC intentionally optimizes for **prototype velocity** while refusing ambiguous observability claims.

---

## 1. Definitions

- **Agentic system**: A system that interprets intent and autonomously executes actions (tool calls, code edits, deployments, messages, etc.).
- **Decision event**: A structured record capturing one committed decision/action boundary, including provenance and evaluation hooks.
- **Provenance**: A reconstructable chain from user request → prompt bundle → model output → tool calls → final actions → impact.
- **Prompt bundle**: The exact effective inputs to the model call (system/dev/user messages + retrieval context + tool availability + parameters).
- **Comparison hooks**: Machine-evaluable checks that compare request/constraints against outputs/actions.
- **Capture modes**: Policies controlling how much sensitive content is stored (full / redacted / hashed).

Normative terms **MUST**, **SHOULD**, **MAY** are as defined in RFC 2119.

---

## 2. Goals and Non-Goals

### 2.1 Goals (Prototype-first)
- Provide a **single event schema** that can be emitted as JSON for every agent step.
- Guarantee **correlation IDs** across the full chain.
- Capture enough context to enable:
  - alignment checks,
  - auditability,
  - incident review,
  - future Decision SLOs.
- Support **provider-agnostic** operation (Claude, Codex, etc.) without relying on hidden internals.
- Provide capture modes that make adoption realistic in real environments.

### 2.2 Non-Goals
- Building a dashboard platform.
- Requiring full chain-of-thought or model internals.
- Enforcing a specific agent framework (LangGraph, Autogen, etc.).
- Perfect semantic evaluation (initial checks can be rule-based and evolve later).

---

## 3. System Invariant (Non-Negotiable)

> **All model interactions and agent actions MUST pass through an instrumentation boundary that emits DecisionEvents.**

If the agent can call the model or tools outside this boundary, the system is not observable in the sense of RFC 0001.

---

## 4. Event Model Overview

This RFC defines a canonical event called **DecisionEvent**.  
DecisionEvent is emitted at **action boundaries**, not at every token.

### 4.1 Action boundary examples
- A model completion is produced and accepted by the agent.
- The agent modifies a file.
- The agent runs tests.
- The agent opens a PR.
- The agent deploys.
- The agent makes an external call (API).
- The agent decides to do nothing (explicit non-action).

---

## 5. DecisionEvent (Canonical Schema)

DecisionEvent MUST be serializable as JSON.

### 5.1 Required Top-Level Fields

```json
{
  "schema_version": "0.2",
  "event_id": "uuid",
  "timestamp": "RFC3339",
  "trace_id": "string",
  "span_id": "string",
  "parent_span_id": "string|null",

  "session": {
    "session_id": "string",
    "run_id": "string",
    "agent_id": "string",
    "agent_version": "string",
    "environment": "local|ci|staging|prod|unknown"
  },

  "request": {
    "request_id": "string",
    "user_request_raw": "string|redacted|hash",
    "constraints": [
      { "id": "string", "type": "style|safety|format|scope|other", "rule": "string" }
    ],
    "context": {
      "channel": "string",
      "repo": "string|null",
      "branch": "string|null",
      "ticket_id": "string|null"
    }
  },

  "prompt_provenance": {
    "provider": "openai|anthropic|other",
    "model": "string",
    "capture_mode": "full|redacted|hashed",
    "prompt_bundle": { },
    "prompt_bundle_hash": "sha256",
    "parameters": {
      "temperature": "number|null",
      "top_p": "number|null",
      "max_tokens": "number|null"
    }
  },

  "model_output": {
    "completion_id": "string|null",
    "output_raw": "string|redacted|hash|null",
    "output_structured": "object|null",
    "tool_calls": [],
    "usage": {
      "input_tokens": "number|null",
      "output_tokens": "number|null",
      "latency_ms": "number|null"
    }
  },

  "agent_action": {
    "action_type": "plan|edit|run_tests|command|open_pr|merge|deploy|api_call|message|no_op|other",
    "action_summary": "string",
    "artifacts": [],
    "tool_results": []
  },

  "evaluation": {
    "alignment": {
      "status": "pass|warn|fail|unknown",
      "score": "number|null",
      "violations": []
    },
    "quality": {
      "status": "pass|warn|fail|unknown",
      "checks": []
    },
    "policy": {
      "status": "pass|warn|fail|unknown",
      "checks": []
    }
  }
}
```

### 5.2 Field Semantics (Normative)

* `schema_version` MUST be present and semver-like.

* `event_id` MUST be globally unique.

* `trace_id` MUST remain constant for the entire agent run.

* `span_id` MUST be unique per event; `parent_span_id` MUST form a tree/graph of actions.

* `request.user_request_raw` MUST be captured in one of the capture modes (full/redacted/hashed).

* `request.constraints` MUST represent explicit constraints derived from the user request and system policy.

  * Prototype note: constraints can be manually specified at first.

* `prompt_provenance.prompt_bundle` MUST contain the *effective* prompt inputs:

  * system messages,
  * developer messages,
  * user messages,
  * retrieved context (if any),
  * tool availability,
  * any intermediate prompt transformations.

* `prompt_bundle_hash` MUST be the hash of a deterministic serialization of the prompt bundle.

* `model_output.output_raw` MUST be captured (full/redacted/hashed) when a completion exists.

* `model_output.tool_calls` MUST include any tool invocation requested by the model.

* `agent_action.tool_results` MUST include the results returned to the agent.

* `evaluation` MUST exist even if checks are `unknown`.

  * The absence of evaluation MUST be considered an observability failure.

---

## 6. Prompt Bundle (Required Structure)

The prompt bundle MUST be a structured object containing at least:

```json
{
  "messages": [
    { "role": "system", "content": "string|redacted|hash" },
    { "role": "developer", "content": "string|redacted|hash" },
    { "role": "user", "content": "string|redacted|hash" }
  ],
  "retrieval": {
    "enabled": "boolean",
    "sources": [],
    "snippets": "string|redacted|hash|null"
  },
  "tools": [
    { "name": "string", "description": "string|null", "schema": "object|null" }
  ],
  "transformations": [
    { "type": "template|rewrite|summarize|other", "summary": "string" }
  ]
}
```

### 6.1 Requirements

* The prompt bundle MUST represent what was *actually sent*, not what was intended.
* If the system rewrites prompts, the transformation MUST be recorded.
* Tool availability MUST be recorded, because it constrains agent behavior.

---

## 7. Capture Modes (Full / Redacted / Hashed)

Because prompts and outputs may contain sensitive information, the system MUST support:

### 7.1 Full Capture

* Stores prompt and output content.
* Allowed only in controlled environments.

### 7.2 Redacted Capture

* Stores content with PII/secrets removed or replaced with placeholders.
* Redaction rules MUST be documented and testable.

### 7.3 Hashed Capture

* Stores only hashes + metadata, not raw content.
* Used when storage of raw prompts/outputs is unacceptable.

### 7.4 Normative Requirements

* `capture_mode` MUST be recorded per model call.
* Even in `hashed` mode, the system MUST store:

  * `prompt_bundle_hash`,
  * `output_hash` (via `output_raw: "hash"`),
  * token usage and latency (if available),
  * evaluation results.

---

## 8. Comparison Hooks (Prototype-Friendly Evaluation)

This RFC does not require perfect semantic judges.
It requires a **consistent, machine-usable evaluation surface**.

### 8.1 Alignment Evaluation

The system MUST produce:

* `status`: pass|warn|fail|unknown
* `violations[]`: structured list

Example violation:

```json
{
  "id": "constraint.no_emojis",
  "severity": "warn",
  "message": "Output contains emoji despite 'no emojis' constraint.",
  "evidence": "🙂"
}
```

### 8.2 Minimum Required Checks (Recommended for POC)

For a coding agent POC, implement at least:

* **Format constraints** (e.g., “must output JSON”)
* **Scope constraints** (e.g., “do not modify infra/CI”)
* **Safety constraints** (e.g., “do not exfiltrate secrets”)
* **Repo constraints** (e.g., only under `src/`)

### 8.3 Human Override Hooks

* If a human intervenes (even retrospectively), the system SHOULD emit a DecisionEvent with `action_type = "override"` or annotate the relevant events.

---

## 9. Coding Agent Specific Artifacts (Required for POC)

When `agent_action.action_type` involves code, the system MUST record artifact summaries.

### 9.1 Artifacts structure

```json
{
  "type": "file_edit|command|test_run|pr|commit|diff",
  "id": "string",
  "summary": "string",
  "content_ref": "string|null",
  "hash": "sha256",
  "metadata": {
    "path": "string|null",
    "lines_added": "number|null",
    "lines_removed": "number|null",
    "exit_code": "number|null"
  }
}
```

### 9.2 Requirements

* File changes MUST be representable as diffs or references.
* Commands executed MUST include command string in the selected capture mode.
* Test runs SHOULD include:

  * command,
  * exit code,
  * high-level summary.

---

## 10. Failure Modes (What MUST be treated as failures)

The following MUST be treated as observability failures:

* Model calls without recorded prompt bundle.
* Agent actions without correlation IDs.
* Missing capture mode.
* Missing evaluation object.
* Unrecorded prompt transformations.
* Tool calls without tool results.

---

## 11. Interop Notes (OpenTelemetry-friendly)

This RFC is compatible with the OpenTelemetry mental model:

* `trace_id` and `span_id` map naturally to OTel spans.
* DecisionEvent MAY be exported as logs with trace correlation.

Interop is optional for POC but SHOULD be kept in mind.

---

## 12. Prototype Implementation Plan (One-Month POC)

This RFC assumes prototyping with a single agent run pipeline.

### Week 1

* Implement instrumentation boundary (wrapper for model calls + tool calls).
* Emit DecisionEvent JSONL to disk.

### Week 2

* Add artifact capture for code edits, commands, test runs.
* Add capture modes (full + redacted at minimum).

### Week 3

* Add baseline evaluation checks (format/scope/safety rules).
* Add violation reporting.

### Week 4

* Produce a minimal “run report”:

  * summary JSON combining events,
  * top violations,
  * timeline of actions.

---

## 13. Future Work

* RFC 0003: Decision SLOs & Error Budgets
* RFC 0004: Reasoning Postmortems
* Reference SDKs for Python/TypeScript
* Optional judge-model evaluation (pluggable)

---

## 14. Final Statement

For agentic prototyping, observability must be **mechanical**, not interpretive:

* events,
* provenance,
* artifacts,
* evaluation surfaces.

If the agent can act without leaving this trail, you do not have an agent system—you have a black box with side effects.


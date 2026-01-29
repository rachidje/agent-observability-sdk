# Data Contract — Black-box DecisionEvents (POC)

## Purpose
Define the minimal, non-ambiguous data contract for `events.jsonl` emitted by the black-box observed runner (Claude Code CLI on macOS).

This contract specifies:
- mandatory fields and allowed values,
- how to represent **`unknowns`**,
- cross-event invariants (trace and ordering),
- forbidden patterns (implicit inference).

This is a POC contract: minimal but strict.

---

## 1) File Contract: **`events.jsonl`**

### 1.1 Format
- `events.jsonl` MUST be UTF-8.
- Each line MUST be a valid JSON object.
- Events MUST be append-only (no rewriting).
- Lines MUST be time-ordered by `timestamp` (monotonic non-decreasing).

### 1.2 Event Count
- A minimally compliant run MUST contain the 9 events defined in `events-blackbox.md`, in the normative order.

---

## 2) DecisionEvent: Required Top-Level Fields

Every event line MUST contain the following top-level fields:

- `schema_version` (string, required)
- `event_id` (string, required, globally unique per event)
- `timestamp` (string, required, RFC3339 UTC recommended)
- `trace_id` (string, required, constant for the run)
- `span_id` (string, required, unique within run)
- `parent_span_id` (string|null, required)
- `observability_mode` (string, required, MUST equal `"black_box"`)

- `session` (object, required)
- `request` (object, required)
- `prompt_provenance` (object, required)
- `model_output` (object, required)
- `agent_action` (object, required)
- `evaluation` (object, required)

---

## 3) Cross-Event Invariants (Run-Level)

### 3.1 Trace invariants
- `trace_id` MUST be identical for all events in a run.
- `span_id` MUST be unique within a run.
- `parent_span_id` MUST reference an earlier `span_id` OR be `null` for the root.

### 3.2 Ordering invariants
- The event order MUST follow the catalog in `events-blackbox.md`.
- If an event is missing, the run is non-compliant.

### 3.3 Mode invariants
- `observability_mode` MUST always be `"black_box"`.
- No event in a black-box run may claim internal prompt visibility.

---

## 4) Field Contracts

## 4.1 session (required)
`session` MUST contain:

- `session_id` (string) — scenario_id
- `run_id` (string)
- `agent_id` (string) — MUST be `"claude-code"` for this POC
- `agent_version` (string) — may be `"unknown"`
- `environment` (string) — one of: `local|ci|staging|prod|unknown`

---

## 4.2 request (required)
`request` MUST contain:

- `request_id` (string)
- `user_request_raw` (string) OR `"redacted"` OR `"hash"`
- `constraints` (array of constraint objects; may be empty in some events)
- `context` (object; may be empty)

### 4.2.1 constraint object
Each constraint MUST include:
- `id` (string)
- `type` (string) — one of: `style|safety|format|scope|quality|other`
- `rule` (string)

### 4.2.2 Minimum constraints for this POC
If present in the scenario, the runner MUST emit these constraints at least once:
- `output.json_only` (format)
- `style.no_emojis` (style)
- `scope.no_ci_changes` (scope)
- `quality.tests_required` (quality)

---

## 4.3 prompt_provenance (required, black-box semantics)
`prompt_provenance` MUST contain:

- `provider` (string) — recommended: `"anthropic"`; may be `"unknown"`
- `model` (string) — may be `"unknown"`
- `capture_mode` (string) — one of: `full|redacted|hashed`
- `prompt_bundle` (object|null) — MUST be `null` in black-box mode
- `prompt_bundle_hash` (string) — MUST be `"unknown"` in black-box mode
- `parameters` (object) — may contain:
  - `temperature` (number|null)
  - `top_p` (number|null)
  - `max_tokens` (number|null)

### 4.3.1 Black-box rule (strict)
In black-box mode:
- `prompt_bundle` MUST be `null`.
- `prompt_bundle_hash` MUST be `"unknown"`.
- Any other value is a contract violation (it implies internal prompt access).

---

## 4.4 model_output (required, black-box semantics)
`model_output` MUST contain:

- `completion_id` (string|null) — SHOULD be null in black-box
- `output_raw` (string|null) — may be `"captured_as_artifact"` or null
- `output_structured` (object|null)
- `tool_calls` (array) — MUST be empty `[]` in black-box
- `usage` (object) — may contain:
  - `input_tokens` (number|null)
  - `output_tokens` (number|null)
  - `latency_ms` (number|null)

### 4.4.1 Black-box rule (strict)
In black-box mode:
- `tool_calls` MUST be `[]`.
- Any non-empty value is a contract violation.

---

## 4.5 agent_action (required)
`agent_action` MUST contain:

- `action_type` (string) — one of:
  `plan|edit|run_tests|command|open_pr|merge|deploy|api_call|message|no_op|other`
- `action_summary` (string)
- `artifacts` (array)
- `tool_results` (array) — MUST be empty in black-box unless the runner itself uses tools

### 4.5.1 artifacts (array of artifact objects)
Each artifact MUST include:
- `type` (string) — e.g. `stdout_log|stderr_log|diff|command_log|process|metadata|summary`
- `id` (string)
- `summary` (string)
- `content_ref` (string|null) — relative path recommended
- `hash` (string) — e.g. `sha256:...`
- `metadata` (object) — may be empty

### 4.5.2 Required artifacts for minimal compliance
A minimally compliant run MUST reference:
- stdout_log (`claude_stdout.txt`)
- stderr_log (`claude_stderr.txt`)
- diff (`fs_diff.patch`)
And MUST reference `command_log` if wrappers are enabled and produced logs.

---

## 4.6 evaluation (required)
`evaluation` MUST contain:

- `alignment` (object)
- `quality` (object)
- `policy` (object)

Each sub-object MUST contain:
- `status` (string) — one of: `pass|warn|fail|unknown`
- `score` (number|null) — optional, may be null
- `violations` (array) OR `checks` (array) as defined below

### 4.6.1 alignment
`alignment` MUST contain:
- `status`
- `score` (number|null)
- `violations` (array)

### 4.6.2 quality
`quality` MUST contain:
- `status`
- `checks` (array)

### 4.6.3 policy
`policy` MUST contain:
- `status`
- `checks` (array)

### 4.6.4 violation object (required shape)
Each violation MUST include:
- `id` (string)
- `severity` (string) — one of: `warn|fail`
- `message` (string)
- `evidence` (string) — bounded excerpt OR hash reference

### 4.6.5 check object (required shape)
Each check MUST include:
- `id` (string)
- `status` (string) — one of: `pass|warn|fail|unknown`
- `evidence` (string)

---

## 5) Unknowns: Representation Rules

Unknowns MUST be explicit and stable.

### 5.1 Forbidden ambiguity
- DO NOT use `null` to mean "unknown" unless the field contract explicitly allows null.
- DO NOT omit required fields.

### 5.2 Canonical unknown values (POC)
Use these values:
- `"unknown"` for strings
- `null` only where the contract allows it
- `[]` for arrays that must be empty in black-box (e.g. tool_calls)

Examples:
- `prompt_bundle_hash: "unknown"`
- `agent_version: "unknown"`

---

## 6) Forbidden Patterns (Hard Fail)

A run is invalid if any event:
- contains a non-null `prompt_provenance.prompt_bundle`
- contains non-empty `model_output.tool_calls`
- invents reasoning or intent in `action_summary` (e.g., "agent believed", "agent inferred")
- sets evaluation outcomes without referencing evidence sources (stdout/diff/command logs)

---

## 7) Minimal Evidence Requirements

When setting statuses to `pass|warn|fail`, the runner MUST provide evidence:
- from `fs_diff.patch` (observed),
- from `command_logs.jsonl` (observed, if available),
- or from stdout/stderr artifacts (declared, non-normative).

Evidence MUST be bounded:
- excerpts MUST be short,
- otherwise reference by hash.

---

## 8) White-box Compatibility (Future)

This contract is designed to expand in white-box mode:
- `prompt_bundle` may become non-null
- `tool_calls` may become non-empty
- additional events may appear

However, black-box runs MUST continue to follow this contract unchanged
to preserve comparability across modes.

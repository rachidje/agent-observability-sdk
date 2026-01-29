# Black-box Events — DecisionEvent Catalog (Claude Code CLI)

## Purpose
Define the exact DecisionEvents emitted by the black-box observed runner
for a single agent run (Claude Code CLI), including:
- event types,
- ordering,
- required fields,
- referenced artifacts,
- what is considered observed vs unknown.

This document is normative for the POC.

---

## Global Requirements (All Events)

All DecisionEvents MUST include:
- `schema_version`
- `event_id`
- `timestamp` (RFC3339)
- `trace_id` (constant for the run)
- `span_id` (unique per event)
- `parent_span_id` (forms a tree)
- `observability_mode: "black_box"`

All events MUST include `session` with:
- `session_id` (scenario_id)
- `run_id`
- `agent_id: "claude-code"`
- `agent_version` (if unknown, set `"unknown"`)
- `environment: "local|ci|staging|prod|unknown"`

All events MUST include `evaluation` (even if unknown):
- `alignment.status`
- `quality.status`
- `policy.status`

Unknown data MUST remain unknown. No inference.

---

## Observed vs Declared vs Unknown

### Observed (source of truth)
- filesystem diff (before/after)
- wrapper command logs (if enabled)
- process metadata (exit code, duration)

### Declared (non-normative artifacts)
- agent stdout/stderr
- verbose traces

### Unknown (must remain unknown)
- internal prompts / prompt bundle
- internal tool routing
- chain-of-thought / reasoning
- retrieval context injected by the CLI

---

## Event List (Normative Order)

A run MUST emit the following events in order:

1) `run_started`  
2) `workspace_prepared`  
3) `agent_invoked`  
4) `agent_completed`  
5) `artifacts_captured`  
6) `fs_diff_captured`  
7) `commands_observed` (or `commands_observation_unavailable`)  
8) `evaluation_performed`  
9) `run_finished`

---

## 1) Event: run_started

### When
Immediately after creating `run_id` and initializing run directories.

### Required Fields
- `agent_action.action_type = "other"`
- `agent_action.action_summary` includes run_id + scenario_id

### Artifacts
- MUST reference `metadata.json` if created at this point
  (otherwise reference it in `workspace_prepared`)

---

## 2) Event: workspace_prepared

### When
After the workspace is materialized (empty or copied from existing).

### Required Fields
- `agent_action.action_type = "other"`
- MUST include `request` with:
  - `request_id`
  - `user_request_raw` (full/redacted/hash)
  - `constraints[]`

### Required Request Constraints (POC)
The runner MUST emit at least these constraints if present in scenario:
- `output.json_only`
- `style.no_emojis`
- `scope.no_ci_changes`
- `quality.tests_required`

### Artifacts
- MAY reference a workspace manifest (optional)
- MUST include workspace root path in artifact metadata (non-sensitive)

---

## 3) Event: agent_invoked

### When
Immediately before starting the Claude Code CLI process.

### Required Fields
- `agent_action.action_type = "plan"` (or `"other"` if you prefer strictness)
- `agent_action.action_summary` MUST mention:
  - verbose enabled/disabled
  - cwd = workspace

### Artifacts
- MUST include a `process` artifact with:
  - cwd
  - argv (hash or full, depending on capture_mode)
  - start timestamp

### Notes
This event does NOT claim anything about internal prompts.

---

## 4) Event: agent_completed

### When
Immediately after Claude Code process ends.

### Required Fields
- `agent_action.action_type = "other"`
- `agent_action.action_summary` MUST include:
  - exit_code
  - duration_ms

### Artifacts
- MUST include a `process` artifact (completion metadata)
- MUST NOT embed stdout/stderr here (keep as artifacts later)

---

## 5) Event: artifacts_captured

### When
After stdout/stderr are persisted as artifacts.

### Required Fields
- `agent_action.action_type = "other"`
- `model_output.output_raw = "captured_as_artifact"` (or null)
- MUST include `artifacts`:
  - `claude_stdout.txt`
  - `claude_stderr.txt`

### Artifact Metadata Requirements
Each stdout/stderr artifact MUST mark:
- `non_normative: true`
- `hash`
- `content_ref`

---

## 6) Event: fs_diff_captured

### When
After computing filesystem diff (before/after).

### Required Fields
- `agent_action.action_type = "edit"`
- MUST include `artifacts` containing:
  - `fs_diff.patch`

### Artifact Metadata Requirements
- MUST include list of changed paths (bounded; if too large, include top-N + count)
- MUST include diff hash
- MUST include diff generation method:
  - `git_diff` | `diff_ru` | `other`

---

## 7) Event: commands_observed

### When
If PATH wrappers are enabled and command logs exist.

### Required Fields
- `agent_action.action_type = "command"` or `"run_tests"` (if tests detected)
- MUST reference `artifacts/command_logs.jsonl`
- MUST include note that only wrapped binaries are captured

### Minimum Artifact Metadata
- `observed_count`
- `categories_seen` (if classified)

---

## 7b) Event: commands_observation_unavailable

### When
If PATH wrappers are not enabled or produced no data.

### Required Fields
- `agent_action.action_type = "other"`
- `agent_action.action_summary` must state why unavailable:
  - wrappers disabled
  - no wrapped binaries invoked
  - permission issue
  - unknown

### Evaluation Impact
- `quality.tests_required` MUST NOT be failed solely due to unavailable command observation.
  It MAY be warned and rely on filesystem evidence.

---

## 8) Event: evaluation_performed

### When
After all artifacts are available and checks are computed.

### Required Fields
- `evaluation.alignment.status` MUST be set
- `evaluation.policy.status` MUST be set
- `evaluation.quality.status` MUST be set

### Required Checks (POC)

#### Policy
- `scope.no_ci_changes`
- `style.no_emojis`

#### Quality
- `quality.tests_required`

#### Alignment
- `output.json_only`

### Violation Format (Required)
Each violation MUST include:
- `id`
- `severity` (warn|fail)
- `message`
- `evidence` (bounded excerpt or a hash reference)

### Evidence Sources
- stdout/stderr (declared)
- fs_diff.patch (observed)
- command_logs.jsonl (observed if available)

---

## 9) Event: run_finished

### When
At the very end, after persisting all outputs.

### Required Fields
- `agent_action.action_type = "other"`
- Summary MUST include overall statuses:
  - alignment, quality, policy

### Artifacts
- MAY include a compact run summary artifact (optional)
- MUST NOT replace the raw events (raw events remain primary)

---

## Minimal Compliance Checklist (POC)

A run is considered minimally compliant if:
- all 9 events are present in order,
- `fs_diff.patch` exists and is referenced,
- stdout/stderr artifacts exist and are referenced,
- evaluation_performed exists with statuses set,
- unknown fields remain unknown (no fabricated prompt provenance).

---

## White-box Compatibility Rule

This catalog MUST remain stable when moving to white-box.
White-box mode will:
- fill `prompt_provenance.prompt_bundle`
- fill `model_output.tool_calls`
- add additional events if needed

But these black-box events MUST still be emit-able to preserve comparability.

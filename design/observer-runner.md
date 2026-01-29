# Observed Runner — Black-box Harness (Claude Code CLI)

## Purpose
Run a black-box coding agent (Claude Code CLI) inside an observed sandbox
and emit machine-readable DecisionEvents describing what happened,
without relying on internal model access.

This runner is an instrumentation tool, not an agent.

---

## Scope
- OS: macOS
- Agent: Claude Code (CLI)
- Observability mode: black-box
- Output: append-only `events.jsonl` + artifacts

---

## Responsibilities

The observed runner MUST:
1. Create an isolated workspace (empty or existing)
2. Execute Claude Code CLI with the raw user request
3. Capture observable effects only
4. Emit DecisionEvents derived from those observations
5. Never infer internal intent or reasoning

The runner MUST NOT:
- Modify agent behavior
- Inject corrective logic
- Rewrite or fabricate events
- Interpret model reasoning

---

## Inputs

- scenario.md (source of truth)
- parameters.json
- workspace_mode: empty | existing
- capture_mode: full | redacted | hashed

---

## Outputs (per run)
```
runs/<run_id>/
├── metadata.json
├── events.jsonl
├── artifacts/
│   ├── claude_stdout.txt
│   ├── claude_stderr.txt
│   ├── fs_diff.patch
│   └── command_logs.jsonl (optional)
└── workspace/
```
---

## Execution Flow

1. Initialize **`run_id`** (timestamp-based)
2. Materialize workspace
3. Snapshot filesystem (before)
4. Prepare PATH wrappers (optional)
5. Execute Claude Code CLI
6. Capture **`stdout`** / **`stderr`**
7. Snapshot filesystem (after)
8. Compute filesystem **`diff`**
9. Run evaluation checks
10. Emit **`DecisionEvents`**
11. Close run

---

## Observation Sources

### Filesystem
- Snapshot diff before/after execution
- Source of truth for code changes

### Process Output
- stdout/stderr captured verbatim
- Treated as non-normative artifacts

### Command Observation (Optional)
- PATH wrappers for selected binaries
- One JSON line per observed command

---

## DecisionEvent Emission Rules

**`DecisionEvents`** are emitted:
- At run start
- After agent execution
- After filesystem diff computation
- After command observation
- After evaluation
- At run end

Events are:
- Append-only
- Time-ordered
- Derived from observable facts only

---

## Evaluation (POC)

Mechanical checks only:
- CI files modified?
- Tests added?
- Tests executed?
- Final output valid JSON?
- Emojis present in output?

Evaluation results are recorded,
never enforced.

---

## Guarantees

This runner guarantees:
- Reproducible observation
- No hidden inference
- Explicit unknowns
- White-box compatibility later

---

## Explicit Limitations

- No access to internal prompts
- No access to internal tool routing
- No access to model reasoning

Unknown data MUST remain unknown.

---

## Future Extension

This runner is compatible with a future white-box mode where:
- DecisionEvents are emitted internally
- Prompt provenance is available
- Tool calls are first-class events

Schema compatibility MUST be preserved.

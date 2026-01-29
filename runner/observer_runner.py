#!/usr/bin/env python3
"""
observer_runner.py — Black-box Observer Runner for Claude Code CLI.

Creates a run directory, prepares workspace, launches Claude Code CLI,
captures stdout/stderr, computes fs diff, and emits a valid events.jsonl.
"""

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _uuid() -> str:
    return str(uuid.uuid4())


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return f"sha256:{h.hexdigest()}"
    except FileNotFoundError:
        return "sha256:empty"


def _sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _snapshot_tree(root: str) -> dict[str, str]:
    """Return {relative_path: sha256} for every file under *root*.
    Excludes .git/ directory (runner-managed, not workspace content)."""
    snap: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        # skip .git tree entirely
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            snap[rel] = _sha256(full)
    return snap



# ---------------------------------------------------------------------------
# Event builder
# ---------------------------------------------------------------------------

def _base_event(
    trace_id: str,
    run_id: str,
    session_id: str,
    request_id: str,
    parent_span_id: str | None = None,
) -> dict:
    span_id = _uuid()
    return {
        "schema_version": "0.2",
        "event_id": _uuid(),
        "timestamp": _now_iso(),
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "observability_mode": "black_box",
        "session": {
            "session_id": session_id,
            "run_id": run_id,
            "agent_id": "claude-code",
            "agent_version": "unknown",
            "environment": "local",
        },
        "request": {
            "request_id": request_id,
            "user_request_raw": "unknown",
            "constraints": [],
            "context": {},
        },
        "prompt_provenance": {
            "provider": "anthropic",
            "model": "unknown",
            "capture_mode": "full",
            "prompt_bundle": None,
            "prompt_bundle_hash": "unknown",
            "parameters": {
                "temperature": None,
                "top_p": None,
                "max_tokens": None,
            },
        },
        "model_output": {
            "completion_id": None,
            "output_raw": None,
            "output_structured": None,
            "tool_calls": [],
            "usage": {
                "input_tokens": None,
                "output_tokens": None,
                "latency_ms": None,
            },
        },
        "agent_action": {
            "action_type": "other",
            "action_summary": "",
            "artifacts": [],
            "tool_results": [],
        },
        "evaluation": {
            "alignment": {"status": "unknown", "score": None, "violations": []},
            "quality": {"status": "unknown", "checks": []},
            "policy": {"status": "unknown", "checks": []},
        },
    }


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run(
    prompt: str,
    scenario_id: str = "default",
    workspace_source: str | None = None,
    runs_root: str = "runs",
    claude_cmd: str = "claude",
    verbose: bool = False,
) -> str:
    """Execute a single observed run. Returns the run directory path."""

    run_id = _uuid()
    trace_id = _uuid()
    request_id = _uuid()
    run_dir = os.path.join(runs_root, run_id)
    workspace = os.path.join(run_dir, "workspace")
    artifacts_dir = os.path.join(run_dir, "artifacts")

    os.makedirs(run_dir, exist_ok=True)
    os.makedirs(artifacts_dir, exist_ok=True)

    events: list[dict] = []
    root_span: str | None = None

    def _ev(parent: str | None = None) -> dict:
        return _base_event(trace_id, run_id, scenario_id, request_id, parent)

    def emit(event: dict, event_name: str) -> str:
        """Append event to list, return its span_id."""
        event["agent_action"]["action_summary"] = (
            f"[{event_name}] " + event["agent_action"]["action_summary"]
        )
        events.append(event)
        return event["span_id"]

    # -----------------------------------------------------------------------
    # 1) run_started
    # -----------------------------------------------------------------------
    ev = _ev()
    ev["agent_action"]["action_summary"] = f"run_id={run_id} scenario_id={scenario_id}"
    root_span = emit(ev, "run_started")

    # -----------------------------------------------------------------------
    # 2) workspace_prepared
    # -----------------------------------------------------------------------
    if workspace_source and os.path.isdir(workspace_source):
        shutil.copytree(workspace_source, workspace)
    else:
        os.makedirs(workspace, exist_ok=True)

    # Init git so we can diff later
    git_env = {**os.environ, "GIT_AUTHOR_NAME": "runner", "GIT_COMMITTER_NAME": "runner",
               "GIT_AUTHOR_EMAIL": "runner@local", "GIT_COMMITTER_EMAIL": "runner@local"}
    subprocess.run(["git", "init"], cwd=workspace, capture_output=True, env=git_env)
    subprocess.run(["git", "add", "."], cwd=workspace, capture_output=True, env=git_env)
    git_commit_result = subprocess.run(
        ["git", "commit", "-m", "initial", "--allow-empty"],
        cwd=workspace, capture_output=True, env=git_env,
    )
    git_commit_ok = git_commit_result.returncode == 0

    snapshot_before = _snapshot_tree(workspace)

    ev = _ev(root_span)
    ev["request"]["user_request_raw"] = prompt
    ev["request"]["constraints"] = [
        {"id": "output.json_only", "type": "format", "rule": "Output must be JSON only"},
        {"id": "style.no_emojis", "type": "style", "rule": "No emojis in output"},
        {"id": "scope.no_ci_changes", "type": "scope", "rule": "Do not modify CI configuration"},
        {"id": "quality.tests_required", "type": "quality", "rule": "Tests must be present"},
    ]
    ev["agent_action"]["action_summary"] = f"workspace={'copy' if workspace_source else 'empty'} git_initialized_by_runner=true"
    ev["agent_action"]["artifacts"] = [
        {
            "type": "metadata",
            "id": _uuid(),
            "summary": "workspace root",
            "content_ref": "workspace/",
            "hash": "sha256:n/a",
            "metadata": {
                "workspace_root_abs": workspace,
                "git_initialized_by_runner": True,
                "git_commit_success": git_commit_ok,
            },
        }
    ]
    emit(ev, "workspace_prepared")

    # -----------------------------------------------------------------------
    # 3) agent_invoked
    # -----------------------------------------------------------------------
    argv = [claude_cmd, "--print", prompt]
    if verbose:
        argv.insert(1, "--verbose")

    ev = _ev(root_span)
    ev["agent_action"]["action_type"] = "plan"
    ev["agent_action"]["action_summary"] = f"verbose={'yes' if verbose else 'no'} cwd={workspace}"
    ev["agent_action"]["artifacts"] = [
        {
            "type": "process",
            "id": _uuid(),
            "summary": "claude-code invocation",
            "content_ref": None,
            "hash": "sha256:n/a",
            "metadata": {
                "cwd": workspace,
                "argv": argv,
                "start_timestamp": _now_iso(),
            },
        }
    ]
    invoke_span = emit(ev, "agent_invoked")

    # -----------------------------------------------------------------------
    # Launch Claude Code CLI
    # -----------------------------------------------------------------------
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=300,
        )
        exit_code = proc.returncode
        stdout_data = proc.stdout or ""
        stderr_data = proc.stderr or ""
    except subprocess.TimeoutExpired:
        exit_code = -1
        stdout_data = ""
        stderr_data = "TIMEOUT after 300s"
    except FileNotFoundError:
        exit_code = -127
        stdout_data = ""
        stderr_data = f"Command not found: {claude_cmd}"

    duration_ms = int((time.monotonic() - t0) * 1000)

    # -----------------------------------------------------------------------
    # 4) agent_completed
    # -----------------------------------------------------------------------
    ev = _ev(invoke_span)
    ev["agent_action"]["action_summary"] = f"exit_code={exit_code} duration_ms={duration_ms}"
    ev["agent_action"]["artifacts"] = [
        {
            "type": "process",
            "id": _uuid(),
            "summary": "claude-code completion",
            "content_ref": None,
            "hash": "sha256:n/a",
            "metadata": {
                "exit_code": exit_code,
                "duration_ms": duration_ms,
            },
        }
    ]
    completed_span = emit(ev, "agent_completed")

    # -----------------------------------------------------------------------
    # 5) artifacts_captured  (stdout + stderr)
    # -----------------------------------------------------------------------
    stdout_path = os.path.join(artifacts_dir, "claude_stdout.txt")
    stderr_path = os.path.join(artifacts_dir, "claude_stderr.txt")
    with open(stdout_path, "w") as f:
        f.write(stdout_data)
    with open(stderr_path, "w") as f:
        f.write(stderr_data)

    ev = _ev(completed_span)
    ev["model_output"]["output_raw"] = "captured_as_artifact"
    ev["agent_action"]["action_summary"] = "stdout and stderr captured"
    ev["agent_action"]["artifacts"] = [
        {
            "type": "stdout_log",
            "id": _uuid(),
            "summary": "claude_stdout.txt",
            "content_ref": "artifacts/claude_stdout.txt",
            "hash": _sha256_bytes(stdout_data.encode()),
            "metadata": {"non_normative": True},
        },
        {
            "type": "stderr_log",
            "id": _uuid(),
            "summary": "claude_stderr.txt",
            "content_ref": "artifacts/claude_stderr.txt",
            "hash": _sha256_bytes(stderr_data.encode()),
            "metadata": {"non_normative": True},
        },
    ]
    emit(ev, "artifacts_captured")

    # -----------------------------------------------------------------------
    # 6) fs_diff_captured
    # -----------------------------------------------------------------------
    # Stage all changes, then diff --cached (direct path, no fallback needed)
    subprocess.run(["git", "add", "-A"], cwd=workspace, capture_output=True, env=git_env)
    r = subprocess.run(
        ["git", "diff", "--cached", "--no-color"],
        cwd=workspace, capture_output=True, text=True, timeout=30,
    )
    diff_text = r.stdout if r.returncode == 0 else ""

    diff_path = os.path.join(artifacts_dir, "fs_diff.patch")
    with open(diff_path, "w") as f:
        f.write(diff_text)

    snapshot_after = _snapshot_tree(workspace)
    changed = [p for p in set(list(snapshot_before) + list(snapshot_after))
               if snapshot_before.get(p) != snapshot_after.get(p)]

    diff_empty = len(diff_text.strip()) == 0

    ev = _ev(completed_span)
    ev["agent_action"]["action_type"] = "edit" if not diff_empty else "no_op"
    ev["agent_action"]["action_summary"] = f"{len(changed)} file(s) changed" + (" (empty diff)" if diff_empty else "")
    ev["agent_action"]["artifacts"] = [
        {
            "type": "diff",
            "id": _uuid(),
            "summary": "fs_diff.patch",
            "content_ref": "artifacts/fs_diff.patch",
            "hash": _sha256_bytes(diff_text.encode()),
            "metadata": {
                "changed_paths": changed[:50],
                "total_changed": len(changed),
                "method": "git_diff",
            },
        }
    ]
    diff_span = emit(ev, "fs_diff_captured")

    # -----------------------------------------------------------------------
    # 7) commands_observation_unavailable (wrappers not implemented yet)
    # -----------------------------------------------------------------------
    ev = _ev(diff_span)
    ev["agent_action"]["action_summary"] = "wrappers disabled — command observation unavailable"
    cmd_span = emit(ev, "commands_observation_unavailable")

    # -----------------------------------------------------------------------
    # 8) evaluation_performed  (minimal / placeholder)
    # -----------------------------------------------------------------------
    ev = _ev(cmd_span)
    ev["agent_action"]["action_summary"] = "evaluation computed from artifacts"
    ev["evaluation"] = {
        "alignment": {
            "status": "unknown",
            "score": None,
            "violations": [],
        },
        "quality": {
            "status": "unknown",
            "checks": [
                {
                    "id": "quality.tests_required",
                    "status": "unknown",
                    "evidence": "command observation unavailable",
                }
            ],
        },
        "policy": {
            "status": "unknown",
            "checks": [
                {
                    "id": "scope.no_ci_changes",
                    "status": "unknown",
                    "evidence": "diff artifact ref: artifacts/fs_diff.patch",
                },
                {
                    "id": "style.no_emojis",
                    "status": "unknown",
                    "evidence": "stdout artifact ref: artifacts/claude_stdout.txt",
                },
            ],
        },
    }
    emit(ev, "evaluation_performed")

    # -----------------------------------------------------------------------
    # 9) run_finished
    # -----------------------------------------------------------------------
    ev = _ev(root_span)
    ev["agent_action"]["action_summary"] = (
        f"alignment=unknown quality=unknown policy=unknown exit_code={exit_code}"
    )
    emit(ev, "run_finished")

    # -----------------------------------------------------------------------
    # Write events.jsonl
    # -----------------------------------------------------------------------
    events_path = os.path.join(run_dir, "events.jsonl")
    with open(events_path, "w") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"Run completed: {run_dir}")
    print(f"  events:    {events_path}  ({len(events)} events)")
    print(f"  stdout:    {stdout_path}")
    print(f"  stderr:    {stderr_path}")
    print(f"  diff:      {diff_path}")
    print(f"  exit_code: {exit_code}")
    print(f"  duration:  {duration_ms}ms")

    return run_dir


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Black-box Observer Runner for Claude Code CLI")
    parser.add_argument("prompt", help="The prompt to send to Claude Code")
    parser.add_argument("--scenario-id", default="default", help="Scenario identifier")
    parser.add_argument("--workspace-source", default=None, help="Directory to copy as workspace (empty if omitted)")
    parser.add_argument("--runs-root", default="runs", help="Root directory for run outputs")
    parser.add_argument("--claude-cmd", default="claude", help="Claude CLI command")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose mode on Claude CLI")
    args = parser.parse_args()

    run(
        prompt=args.prompt,
        scenario_id=args.scenario_id,
        workspace_source=args.workspace_source,
        runs_root=args.runs_root,
        claude_cmd=args.claude_cmd,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()

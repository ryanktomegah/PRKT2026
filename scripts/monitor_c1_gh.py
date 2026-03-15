#!/usr/bin/env python3
"""
C1 GitHub Actions Monitor — live dashboard for a remote C1 training run.

Polls `gh run view --log` every N seconds, parses the training log lines,
and renders the same 9-stage dashboard as scripts/monitor_c1.py.

Usage:
    python scripts/monitor_c1_gh.py                         # auto-detect latest run
    python scripts/monitor_c1_gh.py --run-id 22817658592
    python scripts/monitor_c1_gh.py --run-id 22817658592 --interval 60
    python scripts/monitor_c1_gh.py --help

Requires: gh CLI authenticated (GH_TOKEN or gh auth login).
PYTHONPATH does not need to be set — this script has no lip imports.
"""

import argparse
import json
import os
import subprocess
import sys
import time

# Reuse stage metadata and TrainingState from the local monitor
_SCRIPT_DIR = __file__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from monitor_c1 import (  # noqa: E402
    BOLD,
    CYAN,
    DIM,
    GREEN,
    RED,
    RESET,
    YELLOW,
    STAGES,
    TrainingState,
    _eta,
    _fmt_elapsed,
)

REPO = "ryanktomegah/PRKT2026"
WORKFLOW_NAME = "Train C1 (Full)"
STALE_SECONDS = 600  # 10 min without new log lines → warn


# ---------------------------------------------------------------------------
# GitHub helpers
# ---------------------------------------------------------------------------

def _gh(*args: str) -> str:
    """Run a gh CLI command and return stdout. Raises on non-zero exit."""
    cmd = ["gh", "--repo", REPO] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"gh error: {result.stderr.strip()}")
    return result.stdout


def _latest_run_id() -> str:
    """Return the run ID of the most recent Train C1 (Full) run."""
    out = _gh("run", "list", "--workflow", WORKFLOW_NAME, "--limit", "1", "--json", "databaseId")
    runs = json.loads(out)
    if not runs:
        raise RuntimeError(f"No runs found for workflow '{WORKFLOW_NAME}'")
    return str(runs[0]["databaseId"])


def _run_status(run_id: str) -> str:
    """Return the run status string: 'in_progress', 'completed', 'failed', etc."""
    out = _gh("run", "view", run_id, "--json", "status,conclusion")
    data = json.loads(out)
    status = data.get("status", "unknown")
    conclusion = data.get("conclusion") or ""
    if status == "completed":
        return conclusion if conclusion else "completed"
    return status


def _job_id(run_id: str) -> str:
    """Return the first job ID for the run."""
    out = _gh("run", "view", run_id, "--json", "jobs")
    data = json.loads(out)
    jobs = data.get("jobs", [])
    if not jobs:
        raise RuntimeError(f"No jobs found for run {run_id}")
    return str(jobs[0]["databaseId"])


def _fetch_log(job_id: str) -> str:
    """Fetch the full log text for a job."""
    cmd = ["gh", "--repo", REPO, "run", "view", "--log", f"--job={job_id}"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    # gh may return non-zero if log is still streaming — still capture output
    return result.stdout


# ---------------------------------------------------------------------------
# Dashboard rendering
# ---------------------------------------------------------------------------

def _render_gh(
    state: TrainingState,
    run_id: str,
    job_id: str,
    run_status: str,
    log_lines_total: int,
    last_update: float,
    poll_interval: int,
) -> str:
    now = time.time()
    width = 66

    lines = []
    border = "═" * width

    # Status indicator
    if run_status in ("success", "completed"):
        status_str = f"{GREEN}COMPLETE{RESET}"
    elif run_status in ("failure", "cancelled", "timed_out"):
        status_str = f"{RED}{run_status.upper()}{RESET}"
    elif state.completed:
        status_str = f"{GREEN}COMPLETE (log){RESET}"
    else:
        status_str = f"{GREEN}RUNNING{RESET}"

    elapsed = _fmt_elapsed(now - state.started_at.timestamp()) if state.started_at else "—"
    started = state.started_at.strftime("%H:%M:%S") if state.started_at else "—"
    eta_str = _eta(state) or f"{DIM}—{RESET}"

    lines.append(f"\n{BOLD}{border}{RESET}")
    lines.append(f"  {BOLD}C1 GH Actions Monitor{RESET}  |  run {run_id}  |  {status_str}")
    lines.append(f"  Started: {started}  |  Elapsed: {elapsed}  |  ETA: {eta_str}")
    lines.append(f"{BOLD}{border}{RESET}")

    # Stage table
    lines.append(f"  {'S':<4} {'Description':<30} {'Status':<22} {'Time':>6}")
    lines.append(f"  {'─'*60}")

    for idx, (key, name, _, n_epochs) in enumerate(STAGES):
        snum = f"S{idx+1}"
        if state.stage_done[key]:
            t = state.stage_time.get(key)
            t_str = f"{t:.1f}s" if t else "done"
            status_col = f"{GREEN}done{RESET}"
            time_col = f"{DIM}{t_str}{RESET}"
        elif state.current_stage == key and not state.stage_done[key]:
            if key == "s5" and state.s5_epoch > 0:
                detail = f"ep {state.s5_epoch}/5  loss={state.s5_loss:.5f}" if state.s5_loss else f"ep {state.s5_epoch}/5"
                status_col = f"{YELLOW}running{RESET} {DIM}{detail}{RESET}"
            elif key == "s6" and state.s6_epoch > 0:
                detail = f"ep {state.s6_epoch}/5  loss={state.s6_loss:.5f}" if state.s6_loss else f"ep {state.s6_epoch}/5"
                status_col = f"{YELLOW}running{RESET} {DIM}{detail}{RESET}"
            elif key == "s7" and state.s7_epoch > 0:
                auc_str = f"  auc={state.s7_auc:.4f}" if state.s7_auc else ""
                detail = f"ep {state.s7_epoch}/{state.s7_total_epochs}  loss={state.s7_loss:.5f}{auc_str}"
                status_col = f"{YELLOW}running{RESET} {DIM}{detail}{RESET}"
            else:
                status_col = f"{YELLOW}running...{RESET}"
            time_col = ""
        else:
            status_col = f"{DIM}pending{RESET}"
            time_col = ""

        lines.append(f"  {snum:<4} {name:<30} {status_col:<22} {time_col:>6}")

    lines.append(f"  {'─'*60}")

    # Metrics
    best_auc_str = f"{GREEN}{state.s7_best_auc:.4f}{RESET}" if state.s7_best_auc else f"{DIM}—{RESET}"
    threshold_str = f"{GREEN}{state.threshold:.4f}{RESET}" if state.threshold else f"{DIM}—{RESET}"
    lines.append(f"  Best AUC: {best_auc_str}  |  Threshold: {threshold_str}")
    lines.append(f"  Log lines: {log_lines_total}  |  Poll: {poll_interval}s  |  Job: {job_id}")

    # Stale warning
    log_age = now - last_update
    if log_age > STALE_SECONDS and not state.completed and run_status == "in_progress":
        lines.append(f"  {RED}WARNING: no new log lines for {log_age/60:.1f} min — job may be stalled{RESET}")

    lines.append(f"  View: https://github.com/{REPO}/actions/runs/{run_id}")
    lines.append(f"{BOLD}{border}{RESET}\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run(run_id: str, poll_interval: int) -> None:
    print(f"\n{CYAN}C1 GH Monitor — fetching job ID for run {run_id}...{RESET}")
    try:
        job_id = _job_id(run_id)
    except RuntimeError as e:
        print(f"{RED}Error: {e}{RESET}")
        sys.exit(1)

    print(f"{CYAN}Job ID: {job_id}. Polling every {poll_interval}s...{RESET}\n")

    state = TrainingState()
    last_update = time.time()
    lines_seen = 0

    try:
        while True:
            # Fetch run status
            try:
                status = _run_status(run_id)
            except RuntimeError:
                status = "in_progress"

            # Fetch log
            try:
                log_text = _fetch_log(job_id)
                all_lines = log_text.splitlines()
                new_lines = all_lines[lines_seen:]
                if new_lines:
                    last_update = time.time()
                    for line in new_lines:
                        # gh log format: "TIMESTAMP\tJOB_NAME\tSTEP_NAME\tLOG_LINE"
                        # Extract the actual log content (last tab-separated field)
                        parts = line.split("\t", 3)
                        log_line = parts[-1] if len(parts) >= 4 else line
                        state.parse_line(log_line)
                    lines_seen = len(all_lines)
            except RuntimeError:
                pass  # transient gh error — keep polling

            # Render dashboard
            dashboard = _render_gh(
                state, run_id, job_id, status,
                lines_seen, last_update, poll_interval,
            )
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.write(dashboard)
            sys.stdout.flush()

            # Exit conditions
            if state.completed or status in ("success", "failure", "cancelled", "timed_out"):
                if state.completed or status == "success":
                    print(f"{GREEN}{BOLD}Training complete!{RESET}\n")
                else:
                    print(f"{RED}Run ended with status: {status}{RESET}\n")
                    print(f"View logs: gh run view --log --job={job_id} --repo {REPO}\n")
                break

            time.sleep(poll_interval)

    except KeyboardInterrupt:
        print(f"\n{YELLOW}Monitor stopped (Ctrl-C). Training continues on GitHub Actions.{RESET}")
        print(f"Resume: python scripts/monitor_c1_gh.py --run-id {run_id}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Live dashboard for C1 training running on GitHub Actions."
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="GitHub Actions run ID (default: auto-detect latest Train C1 run)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Poll interval in seconds (default: 30; min: 10)",
    )
    args = parser.parse_args()

    poll_interval = max(10, args.interval)

    if args.run_id:
        run_id = args.run_id
    else:
        print(f"{CYAN}Auto-detecting latest '{WORKFLOW_NAME}' run...{RESET}")
        try:
            run_id = _latest_run_id()
            print(f"{CYAN}Found run ID: {run_id}{RESET}")
        except RuntimeError as e:
            print(f"{RED}Error: {e}{RESET}")
            sys.exit(1)

    run(run_id, poll_interval)


if __name__ == "__main__":
    main()

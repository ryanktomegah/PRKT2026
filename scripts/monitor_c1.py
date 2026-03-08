#!/usr/bin/env python3
"""
C1 Training Monitor — live terminal dashboard for the 9-stage training pipeline.

Usage:
    python scripts/monitor_c1.py --log /tmp/c1_train.log --pid 3073
    python scripts/monitor_c1.py --log /tmp/c1_train.log          # no PID tracking
    python scripts/monitor_c1.py --help

Refreshes every 2 seconds. Exits when training completes or PID dies.
Per-epoch metrics require training to be launched with --log-level DEBUG.
"""

import argparse
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Stage metadata
# ---------------------------------------------------------------------------

STAGES = [
    # (key, display_name, completion_pattern, n_epochs_or_None)
    ("s1", "Data validation",          r"stage1_data_validation: (\d+) valid, (\d+) dropped", None),
    ("s2", "Graph construction",       r"stage2_graph_construction: (\d+) nodes, (\d+) edges", None),
    ("s3", "Feature extraction",       r"stage3_feature_extraction: X=\((\d+), (\d+)\)", None),
    ("s4", "Train/val split",          r"stage4_train_val_split: train=(\d+), val=(\d+)", None),
    ("s5", "GraphSAGE pretrain",       r"stage5_graphsage_pretrain: (\d+) pre-train epochs complete", 5),
    ("s6", "TabTransformer pretrain",  r"stage6_tabtransformer_pretrain: (\d+) pre-train epochs complete", 5),
    ("s7", "Joint training",           r"stage7_joint_training: complete", 50),
    ("s8", "Threshold calibration",    r"stage8_threshold_calibration: threshold=([\d.]+)", None),
    ("s9", "Corridor embeddings",      r"stage9_embedding_generation: (\d+) embeddings generated", None),
]

# Timing lines: "stage1_data_validation:                       0.129 s"
RE_TIMING = re.compile(r"(stage\d_\w+):\s+[\d.]+ s")

# Per-epoch DEBUG metrics
RE_S5_EPOCH = re.compile(r"stage5 pre-train epoch (\d+) — avg_loss=([\d.]+)")
RE_S6_EPOCH = re.compile(r"stage6 pre-train epoch (\d+) — avg_loss=([\d.]+)")
RE_S7_EPOCH = re.compile(r"Joint training epoch (\d+) — avg_loss=([\d.]+)\s+train_auc=([\d.]+)")
RE_S7_CHECKPOINT = re.compile(r"stage7_joint_training: restored best checkpoint \(train_auc=([\d.]+)\)")
RE_S7_START = re.compile(r"stage7_joint_training: (\d+) samples, (\d+) batches/epoch, (\d+) epochs")
RE_COMPLETE = re.compile(r"TrainingPipeline\.run complete — total ([\d.]+) s")

# Artifact files that signal completion (relative to repo root, resolved at runtime)
ARTIFACT_FILES = [
    "artifacts/models/c1_model.pkl",
    "artifacts/models/c1_threshold.txt",
    "artifacts/models/c1_embeddings.pkl",
    "artifacts/models/c1_training_report.json",
]

# ANSI colours
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
DIM    = "\033[2m"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class TrainingState:
    def __init__(self):
        self.stage_done: dict[str, bool] = {s[0]: False for s in STAGES}
        self.stage_detail: dict[str, str] = {s[0]: "" for s in STAGES}
        self.stage_time: dict[str, float] = {}
        self.current_stage: str | None = None

        # Per-epoch progress
        self.s5_epoch: int = 0
        self.s5_loss: float | None = None
        self.s6_epoch: int = 0
        self.s6_loss: float | None = None
        self.s7_epoch: int = 0
        self.s7_loss: float | None = None
        self.s7_auc: float | None = None
        self.s7_best_auc: float | None = None
        self.s7_total_epochs: int = 50
        self.s7_batches_per_epoch: int | None = None

        # Stage 8
        self.threshold: float | None = None

        # Overall
        self.started_at: datetime | None = None
        self.completed: bool = False
        self.total_seconds: float | None = None

        # Log tail tracking
        self.log_last_updated: float = time.time()
        self.log_lines_read: int = 0

        # Epoch timing for ETA
        self.s7_epoch_times: list[float] = []
        self.s7_epoch_start: float | None = None

    def parse_line(self, line: str) -> None:
        """Update state from a single log line."""

        # Extract timestamp from log line ("HH:MM:SS  ...")
        ts_match = re.match(r"(\d{2}:\d{2}:\d{2})", line)

        # Detect training start from S1 info line
        if self.started_at is None and "stage1_data_validation:" in line and ts_match:
            today = datetime.now().date()
            h, m, s = map(int, ts_match.group(1).split(":"))
            self.started_at = datetime(today.year, today.month, today.day, h, m, s)

        # Stage completion patterns
        for stage_key, _, pattern, _ in STAGES:
            if not self.stage_done[stage_key] and re.search(pattern, line):
                self.stage_done[stage_key] = True
                m = re.search(pattern, line)
                if m:
                    self.stage_detail[stage_key] = m.group(0)
                self.current_stage = stage_key
                if stage_key == "s8":
                    tm = re.search(r"threshold=([\d.]+)", line)
                    if tm:
                        self.threshold = float(tm.group(1))
                if stage_key == "s7":
                    self.s7_epoch_start = None  # reset for next stage
                break

        # S7 start info — get total epochs
        m = RE_S7_START.search(line)
        if m:
            self.s7_total_epochs = int(m.group(3))
            self.s7_batches_per_epoch = int(m.group(2))
            self.current_stage = "s7"
            self.s7_epoch_start = time.time()

        # Per-epoch DEBUG metrics
        m = RE_S5_EPOCH.search(line)
        if m:
            self.s5_epoch = int(m.group(1))
            self.s5_loss = float(m.group(2))
            self.current_stage = "s5"

        m = RE_S6_EPOCH.search(line)
        if m:
            self.s6_epoch = int(m.group(1))
            self.s6_loss = float(m.group(2))
            self.current_stage = "s6"

        m = RE_S7_EPOCH.search(line)
        if m:
            epoch = int(m.group(1))
            if epoch > self.s7_epoch:
                # Record timing for ETA
                now = time.time()
                if self.s7_epoch_start is not None and epoch > 1:
                    self.s7_epoch_times.append(now - self.s7_epoch_start)
                    if len(self.s7_epoch_times) > 10:
                        self.s7_epoch_times = self.s7_epoch_times[-10:]
                self.s7_epoch_start = now
            self.s7_epoch = epoch
            self.s7_loss = float(m.group(2))
            self.s7_auc = float(m.group(3))
            self.current_stage = "s7"

        m = RE_S7_CHECKPOINT.search(line)
        if m:
            self.s7_best_auc = float(m.group(1))

        # Completion
        m = RE_COMPLETE.search(line)
        if m:
            self.completed = True
            self.total_seconds = float(m.group(1))


# ---------------------------------------------------------------------------
# Dashboard rendering
# ---------------------------------------------------------------------------

def _fmt_elapsed(seconds: float) -> str:
    td = timedelta(seconds=int(seconds))
    h, rem = divmod(td.seconds, 3600)
    m, s = divmod(rem, 60)
    if td.days:
        h += td.days * 24
    return f"{h:02d}:{m:02d}:{s:02d}"


def _pid_alive(pid: int | None) -> bool:
    if pid is None:
        return True  # unknown
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _count_artifacts(repo_root: Path) -> int:
    return sum(1 for f in ARTIFACT_FILES if (repo_root / f).exists())


def _eta(state: TrainingState) -> str | None:
    """Estimate completion time based on S7 epoch pace."""
    if state.completed:
        return None
    if not state.stage_done["s7"] and state.s7_epoch > 0 and state.s7_epoch_times:
        avg_epoch_s = sum(state.s7_epoch_times) / len(state.s7_epoch_times)
        remaining_epochs = state.s7_total_epochs - state.s7_epoch
        remaining_s = remaining_epochs * avg_epoch_s
        # Add rough estimates for remaining stages
        if not state.stage_done["s8"]:
            remaining_s += 30
        if not state.stage_done["s9"]:
            remaining_s += 60
        eta_dt = datetime.now() + timedelta(seconds=remaining_s)
        return eta_dt.strftime("%H:%M:%S")
    return None


def render(state: TrainingState, pid: int | None, log_path: str, repo_root: Path) -> str:
    """Build full dashboard string."""
    now = time.time()
    width = 62

    lines = []
    border = "═" * width

    # Header
    lines.append(f"\n{BOLD}{border}{RESET}")
    pid_str = f"PID {pid}" if pid else "no PID"
    if state.completed:
        status_str = f"{GREEN}COMPLETE{RESET}"
    elif pid is None or _pid_alive(pid):
        status_str = f"{GREEN}RUNNING{RESET}"
    else:
        status_str = f"{RED}DEAD{RESET}"

    elapsed = _fmt_elapsed(now - state.started_at.timestamp()) if state.started_at else "—"
    started = state.started_at.strftime("%H:%M:%S") if state.started_at else "—"

    lines.append(f"  {BOLD}C1 Training Monitor{RESET}  |  {pid_str}  |  {status_str}")
    lines.append(f"  Started: {started}  |  Elapsed: {elapsed}")
    lines.append(f"{BOLD}{border}{RESET}")

    # Stage table
    lines.append(f"  {'S':<4} {'Description':<28} {'Status':<20} {'Time':>6}")
    lines.append(f"  {'─'*58}")

    for idx, (key, name, _, n_epochs) in enumerate(STAGES):
        snum = f"S{idx+1}"

        if state.stage_done[key]:
            t = state.stage_time.get(key)
            t_str = f"{t:.1f}s" if t else "done"
            status_col = f"{GREEN}done{RESET}"
            time_col = f"{DIM}{t_str}{RESET}"
        elif state.current_stage == key and not state.stage_done[key]:
            # Active stage — show epoch progress
            if key == "s5" and state.s5_epoch > 0:
                detail = f"epoch {state.s5_epoch}/5  loss={state.s5_loss:.5f}" if state.s5_loss else f"epoch {state.s5_epoch}/5"
                status_col = f"{YELLOW}running{RESET} {DIM}{detail}{RESET}"
            elif key == "s6" and state.s6_epoch > 0:
                detail = f"epoch {state.s6_epoch}/5  loss={state.s6_loss:.5f}" if state.s6_loss else f"epoch {state.s6_epoch}/5"
                status_col = f"{YELLOW}running{RESET} {DIM}{detail}{RESET}"
            elif key == "s7" and state.s7_epoch > 0:
                auc_str = f"  auc={state.s7_auc:.4f}" if state.s7_auc else ""
                detail = f"epoch {state.s7_epoch}/{state.s7_total_epochs}  loss={state.s7_loss:.5f}{auc_str}"
                status_col = f"{YELLOW}running{RESET} {DIM}{detail}{RESET}"
            else:
                status_col = f"{YELLOW}running...{RESET}"
            time_col = ""
        else:
            status_col = f"{DIM}pending{RESET}"
            time_col = ""

        # Truncate for display (ANSI codes don't count toward width)
        lines.append(f"  {snum:<4} {name:<28} {status_col:<20} {time_col:>6}")

    lines.append(f"  {'─'*58}")

    # Metrics row
    best_auc_str = f"{GREEN}{state.s7_best_auc:.4f}{RESET}" if state.s7_best_auc else f"{DIM}—{RESET}"
    threshold_str = f"{GREEN}{state.threshold:.4f}{RESET}" if state.threshold else f"{DIM}—{RESET}"
    n_artifacts = _count_artifacts(repo_root)
    eta_str = _eta(state) or f"{DIM}—{RESET}"

    lines.append(f"  Best AUC: {best_auc_str}  |  Threshold: {threshold_str}  |  ETA: {eta_str}")
    lines.append(f"  Artifacts: {n_artifacts}/4  |  Log: {log_path}")

    # Stale log warning
    log_age = now - state.log_last_updated
    if log_age > 300 and not state.completed:
        lines.append(f"  {RED}WARNING: no log update for {log_age:.0f}s — process may be stalled{RESET}")

    lines.append(f"{BOLD}{border}{RESET}\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def tail_file(path: str, state: TrainingState) -> None:
    """Read any new lines from the log file and update state."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        new_lines = lines[state.log_lines_read:]
        if new_lines:
            state.log_last_updated = time.time()
            for line in new_lines:
                state.parse_line(line)
            state.log_lines_read = len(lines)
    except FileNotFoundError:
        pass


def run(log_path: str, pid: int | None, poll_interval: float, repo_root: Path) -> None:
    state = TrainingState()

    print(f"\n{CYAN}C1 Monitor starting — watching {log_path}{RESET}")
    if not Path(log_path).exists():
        print(f"{YELLOW}Log file not found yet — waiting for training to start...{RESET}")

    try:
        while True:
            tail_file(log_path, state)

            dashboard = render(state, pid, log_path, repo_root)
            # Clear screen and reprint
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.write(dashboard)
            sys.stdout.flush()

            if state.completed:
                n = _count_artifacts(repo_root)
                print(f"\n{GREEN}{BOLD}Training complete!{RESET}  {n}/4 artifacts saved.\n")
                break

            # If PID is dead and training never completed, warn but keep watching
            if pid is not None and not _pid_alive(pid) and not state.completed:
                age = time.time() - state.log_last_updated
                if age > 30:
                    print(f"\n{RED}PID {pid} is dead and log has been silent for {age:.0f}s.{RESET}")
                    print(f"Training appears to have terminated. Check {log_path} for errors.\n")
                    break

            time.sleep(poll_interval)

    except KeyboardInterrupt:
        print(f"\n{YELLOW}Monitor stopped (Ctrl-C). Training continues in background.{RESET}")
        if pid:
            print(f"Tail log: tail -f {log_path}")
        print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Live dashboard for C1 training pipeline (9 stages)."
    )
    parser.add_argument(
        "--log",
        default="/tmp/c1_train.log",
        help="Path to training log file (default: /tmp/c1_train.log)",
    )
    parser.add_argument(
        "--pid",
        type=int,
        default=None,
        help="PID of the training process to monitor for liveness",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Polling interval in seconds (default: 2)",
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Repo root for artifact detection (default: auto-detected)",
    )
    args = parser.parse_args()

    run(
        log_path=args.log,
        pid=args.pid,
        poll_interval=args.interval,
        repo_root=Path(args.repo_root),
    )


if __name__ == "__main__":
    main()

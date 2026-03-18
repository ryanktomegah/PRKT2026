#!/usr/bin/env python3
"""Symlinked / duplicated from epg/scripts — single source of truth for pipeline coverage check."""
import subprocess, sys
result = subprocess.run(
    [sys.executable, ".claude/skills/epg/scripts/check_pipeline_coverage.py"],
    capture_output=False,
)
sys.exit(result.returncode)

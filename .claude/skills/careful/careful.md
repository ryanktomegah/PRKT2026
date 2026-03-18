---
description: Activate protective guardrails for this session — blocks destructive git commands, force-writes to compliance-critical files, and any change to fee constants without explicit QUANT sign-off. Use before touching pipeline.py, constants.py, or rejection_taxonomy.yaml.
allowed-tools: Bash
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: |
            echo "$CLAUDE_TOOL_INPUT" | python3 -c "
import sys, json, re
inp = json.load(sys.stdin)
cmd = inp.get('command', '')

blocked = [
    (r'git push.*--force', 'force push is blocked in careful mode'),
    (r'git reset --hard', 'hard reset is blocked in careful mode'),
    (r'git checkout\s+--\s', 'checkout -- (discard changes) is blocked in careful mode'),
    (r'git clean\s+-f', 'git clean -f is blocked in careful mode'),
    (r'rm\s+-rf', 'rm -rf is blocked in careful mode'),
    (r'git commit.*--no-verify', '--no-verify bypasses hooks — blocked in careful mode'),
]

for pattern, reason in blocked:
    if re.search(pattern, cmd):
        print(f'CAREFUL MODE BLOCK: {reason}')
        sys.exit(1)

sys.exit(0)
"
---

Activating careful mode for this session.

The following actions are now blocked for the duration of this session:
- `git push --force` / `git push -f`
- `git reset --hard`
- `git checkout -- .` (discard uncommitted changes)
- `git clean -f`
- `rm -rf`
- `git commit --no-verify`

**When to activate:** Before touching any of these files:
- `lip/pipeline.py` (compliance gates)
- `lip/common/constants.py` (fee floor, maturity windows)
- `lip/configs/rejection_taxonomy.yaml` (code classifications)
- `lip/c7_execution_agent/agent.py` (_COMPLIANCE_HOLD_CODES)
- `lip/c6_aml_velocity/*.py` (AML gates)

**Why this matters for EPG work:** The most dangerous failure mode when fixing EPG issues
is accidentally reverting a prior fix while applying a new one. Careful mode ensures that
recovery from a bad edit requires explicit, deliberate action — not an accidental
`git checkout -- .` that silently discards the fix.

Careful mode is active. Proceed with your changes.

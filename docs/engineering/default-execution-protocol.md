# Default Execution Protocol (Locked In)

This is the mandatory delivery protocol for Codex-driven work in this repository.

## Summary
- Use a `codex/*` feature branch workflow for every task.
- Always do planning and design first, with subagent support for medium/large work.
- Commit and push at the end of each completed task, after checks pass.
- Open a draft PR by default for reviewability and clean traceability.

## Implementation Workflow Per Task
1. Grounding pass (non-mutating): map relevant modules, tests, configs, and attached files before making decisions.
2. Parallel understanding: run subagents adaptively for architecture mapping, risk scanning, and test-impact analysis.
3. Decision-complete plan: produce a concrete build plan (interfaces, data flow, edge cases, tests, rollout constraints).
4. Implementation + verification: execute changes, run targeted tests and lint first, then broader regression as needed.
5. Clean checkpoint: commit with clear scope, push branch, and keep task state review-ready.

## Git and Delivery Standards
- Branch naming: `codex/<task-slug>`.
- Commit policy: one or more scoped commits, then push when task acceptance checks pass.
- PR policy: open draft PR by default with summary, risks, and test evidence.
- No hidden work: every meaningful change path is test-backed or explicitly documented as a gap.

## Assumptions and Defaults
- "Clean" means no ambiguous partial state, attached test signal, and reviewable commit history.
- "Deep understanding" means both system-level impact and file-level behavior are analyzed before coding.
- Subagents are used adaptively in parallel by default (small tasks can stay local when faster and equally safe).

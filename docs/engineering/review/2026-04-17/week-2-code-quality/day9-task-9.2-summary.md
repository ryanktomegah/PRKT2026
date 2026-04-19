# Day 9 Task 9.2 — Rust + Go Dependency Audit

**Date run:** 2026-04-19
**Scope:** 3 Rust projects + 2 Go modules.

## Summary

| Project | Tool | Deps scanned | Result |
|---------|------|--------------|--------|
| `lip/c3/rust_state_machine` | cargo audit | 30 crates | **No vulnerabilities** |
| `lip/c6_aml_velocity/rust_velocity` | cargo audit | 43 crates | **No vulnerabilities** |
| `lip/c7_execution_agent/rust_kill_switch` | cargo audit | 82 crates | **No vulnerabilities** |
| `lip/c5_streaming/go_consumer` | govulncheck | (module) | **No vulnerabilities** |
| `lip/c7_execution_agent/go_offer_router` | govulncheck | (module) | **No vulnerabilities** |

Net verdict: **all 5 native-code projects clean.** No inline fix required.

## Rust — cargo audit

Advisory DB: RustSec (1,049 advisories loaded, 2026-04-19 snapshot).

- **c3 state machine** — 30 crates. Clean. No `Cargo.lock` in repo;
  explicit gitignore entry (library-only crate, `crate-type = ["cdylib", "rlib"]`).
- **c6 velocity** — 43 crates. Clean. Same pattern: gitignored lock,
  library-only.
- **c7 kill switch** — 82 crates. Clean. This project has **both** a `[[bin]]`
  and a `[lib]` section, so cargo auto-generated a fresh `Cargo.lock` during
  audit. Following the existing repo convention (all two pre-existing Rust
  projects gitignore their lock files), I added
  `lip/c7_execution_agent/rust_kill_switch/Cargo.lock` to `.gitignore` in
  this commit. If we later decide to reproducibly lock the binary target,
  we should lift all three gitignore entries at once, not just this one —
  split conventions would be worse than either uniform choice.

Advisory versions noted during scan (informational, not CVEs):
- `pyo3` 0.24.2 → available 0.28.3
- `signal-hook` 0.3.18 → available 0.4.4

These are version-lag notices, not vulnerabilities.

## Go — govulncheck

Both modules clean. govulncheck is Go's official advisory scanner (Go team +
OSV DB).

- `lip/c5_streaming/go_consumer` — Kafka consumer binding to C5.
- `lip/c7_execution_agent/go_offer_router` — gRPC offer routing.

## Actions

- [x] cargo audit on 3 Rust projects → clean.
- [x] govulncheck on 2 Go modules → clean.
- [x] Consolidate Cargo.lock gitignore convention (add rust_kill_switch).
- [ ] *(Informational)* Consider bumping pyo3 0.24 → 0.28 and signal-hook
      0.3 → 0.4 in rust_kill_switch when next touching that code.

## Artefacts

- `cargo-audit.txt` — full cargo audit output for all 3 Rust projects
- `govulncheck.txt` — full govulncheck output for both Go modules

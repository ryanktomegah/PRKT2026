# `lip/dgen/` — Synthetic Data Generation

> **All synthetic training and validation corpora for LIP components.** Owned by the DGEN agent. Every corpus is tagged `SYNTHETIC_CORPUS_*` and must never be confused with real transaction data. Domain-realism constraints come from every team agent simultaneously — ML feature distributions (ARIA), Basel III correlated financials (QUANT), SWIFT BIC topology (NOVA), AML typologies (CIPHER), EU AI Act Art. 10 lineage (REX).

**Source:** `lip/dgen/`
**Module count:** 13 modules
**Owner:** DGEN agent
**Reference doc:** [`../data-pipeline.md`](../data-pipeline.md) — operational guide for running generators

---

## Purpose

Real cross-border payment data is impossible to obtain at training scale: it is held by the banks themselves, governed by GDPR, SWIFT confidentiality, and the FATF tipping-off rules, and most banks legally cannot share it even with a vendor under NDA. LIP cannot wait for real data to train its models, and even when pilot data eventually arrives it will not be enough volume to train GraphSAGE + TabTransformer + LightGBM from scratch.

`lip/dgen/` solves this by generating **domain-realistic synthetic corpora** for every component that needs training data. The corpora are not "fake data with realistic numbers" — they encode constraints from every relevant team agent so that a model trained on the synthetic corpus generalises to real data with minimal adjustment when pilot data arrives.

---

## Modules

### Per-component generators

| File | Generates corpus for | Notes |
|------|----------------------|-------|
| `c1_generator.py` | C1 failure classifier | Includes temporal burst clustering (`_inject_temporal_clustering`), per-BIC risk tiers, isotonic-calibration-ready labels |
| `c2_generator.py` | C2 PD model | Basel III PD calibration, correlated financials. Exported as `generate_pd_training_data_v2`. |
| `c3_generator.py` | C3 repayment engine (settlement-time distributions) | Per-corridor settlement timing |
| `c4_generator.py` | C4 dispute classifier | Multilingual dispute strings + negation cases. Exported as `generate_dispute_corpus`. |
| `c6_generator.py` | C6 AML / velocity | AML typology patterns. **Output is `c6_corpus_*.json` and is gitignored** — see `CLAUDE.md` § Key Rules: AML typology patterns must never be committed (CIPHER refusal rule). |

### Generator infrastructure

| File | Purpose |
|------|---------|
| `generate_all.py` | Top-level entry point: `python -m lip.dgen.generate_all --output-dir artifacts/synthetic` |
| `bic_pool.py` | Realistic SWIFT BIC pool — country distribution, institution types, correlated by corridor |
| `iso20022_payments.py` | ISO 20022 `pacs.002` event construction with the full rejection-code taxonomy |
| `aml_production.py` | Production-grade AML pattern injection (used only with the gitignored corpus) |
| `run_production_pipeline.py` | End-to-end production-corpus generation orchestrator |
| `validator.py` | `validate_corpus`, `CorpusReport` — validates a generated corpus against quality gates (label balance, feature distributions, lineage tags) |
| `statistical_validator_production.py` | Heavier statistical validation for production-grade corpora — KS tests, distribution comparison, leakage detection |
| `web_inspector.py` | Browser-based corpus inspection tool for DGEN review |

---

## Public API

Per `lip/dgen/__init__.py`:

```python
from .c2_generator import generate_pd_training_data_v2
from .c4_generator import generate_dispute_corpus
from .validator import CorpusReport, validate_corpus

__all__ = [
    "generate_dispute_corpus",
    "generate_pd_training_data_v2",
    ...
]
```

The `__init__.py` exposes only the highest-level helpers. Component generators (c1, c3, c6) are accessed by direct import (`from lip.dgen.c6_generator import ...`).

## Domain-realism constraints (from the module docstring)

The DGEN module docstring is explicit about which agent owns which constraint:

| Agent | What they enforce |
|-------|-------------------|
| **ARIA** | ML feature distributions, class balance |
| **QUANT** | Correlated financials, Basel III PD rates |
| **NOVA** | SWIFT BIC topology, payment rail patterns |
| **CIPHER** | AML typologies (structuring, layering, velocity) |
| **REX** | EU AI Act Art. 10 data lineage, temporal splits |

Any contributor adding a new generator must engage all five constraints. Skipping one is a refusal-grade error — DGEN will not call data "good" without reading the generator source to verify field semantics (`CLAUDE.md` § What Agents Will Push Back On).

## Critical safety rules

These come from `CLAUDE.md` and are enforced at code review:

1. **Never commit `c6_corpus_*.json`** — AML typology patterns are CIPHER-prohibited from version control, ever
2. **Never commit `artifacts/`** — model binaries and generated data exceed sensible repo size
3. **Tag every corpus `SYNTHETIC_CORPUS_*`** — the tag is structural; no untagged corpus can pass `validate_corpus`
4. **Temporal clustering caveat**: `_inject_temporal_clustering` modifies RJCT timestamps but never flips labels. Burst windows could span train/test split boundaries if temporal splitting is used (current split is stratified random — safe today, document the caveat if you switch to chronological split). See `PROGRESS.md` for the audit notes.

## Running the generators

```bash
# Generate all corpora at once
PYTHONPATH=. python -m lip.dgen.generate_all --output-dir artifacts/synthetic

# Per-component
PYTHONPATH=. python -c "from lip.dgen.c4_generator import generate_dispute_corpus; \
                        records = generate_dispute_corpus(n_samples=15_000, seed=42)"

# Validate an existing corpus
PYTHONPATH=. python -c "from lip.dgen.validator import validate_corpus; \
                        print(validate_corpus('artifacts/synthetic/c1_corpus.parquet'))"
```

See [`../data-pipeline.md`](../data-pipeline.md) for the full operational guide including training commands.

## Cross-references

- **Operational guide**: [`../data-pipeline.md`](../data-pipeline.md)
- **Training entry point**: `lip/train_all.py`
- **C1 training data card**: [`../c1-training-data-card.md`](../c1-training-data-card.md) — SR 11-7 documentation of the C1 corpus
- **DGEN agent role**: `CLAUDE.md` § Team Agents (DGEN row)
- **CIPHER refusal rule**: `CLAUDE.md` § What Agents Will Push Back On

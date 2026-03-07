"""
dgen — DGEN: Data Generation & Quality Engineer
================================================
Synthetic training corpora for all LIP components.

DGEN applies domain-realism constraints from every team agent:
  ARIA   — ML feature distributions, class balance
  QUANT  — Correlated financials, Basel III PD rates
  NOVA   — SWIFT BIC topology, payment rail patterns
  CIPHER — AML typologies (structuring, layering, velocity)
  REX    — EU AI Act Art.10 data lineage, temporal splits

All corpora are tagged SYNTHETIC_CORPUS_* and must never be
mistaken for real transaction data.

Usage
-----
    python -m lip.dgen.generate_all --output-dir artifacts/synthetic

Or per-component:
    from lip.dgen.c4_generator import generate_dispute_corpus
    records = generate_dispute_corpus(n_samples=15_000, seed=42)
"""
from .c2_generator import generate_pd_training_data_v2
from .c4_generator import generate_dispute_corpus
from .validator import CorpusReport, validate_corpus

__all__ = [
    "generate_dispute_corpus",
    "generate_pd_training_data_v2",
    "validate_corpus",
    "CorpusReport",
]

# LIP Synthetic Data Generation

Generate synthetic training corpora for all LIP components.

## Execution Protocol

1. Ensure `PYTHONPATH=.` is set (repo root)
2. Create output directory: `mkdir -p artifacts/synthetic`
3. Run: `PYTHONPATH=. python -m lip.dgen.generate_all --output-dir artifacts/synthetic`
4. Validate generated data: `PYTHONPATH=. python -m lip.dgen.validator --data-dir artifacts/synthetic`
5. Report: corpus sizes, validation pass/fail, any quality issues

## Component Corpus Map
| Generator | Component | Output | Target Size |
|-----------|-----------|--------|-------------|
| c1 (synthetic_data.py) | C1 Failure Classifier | SWIFT pacs.002 events | 50k+ |
| c2_generator.py | C2 PD Model | Counterparty + corridor data | 50k+ |
| c3_generator.py | C3 Repayment | Settlement event sequences | 30k+ |
| c4_generator.py | C4 Dispute | Multilingual dispute texts | 30k+ |
| c6_generator.py | C6 AML | Transaction velocity patterns | 50k+ |

## Rules
- NEVER commit generated data to git (`artifacts/` is in .gitignore)
- NEVER commit `c6_corpus_*.json` (AML typology patterns — CIPHER security rule)
- Validate SHA256 hashes match after generation
- If validator reports issues, investigate before training
- Run from repo root: `/Users/halil/PRKT2026`

# Patent Claim Verification

Verify that LIP code correctly implements patent claims from Provisional Specification v5.2.

## Claim → Component Mapping

### Independent Claims
| Claim | Description | Component | Key File |
|-------|-------------|-----------|----------|
| 1(a) | Monitor real-time pacs.002 stream | C5 | event_normalizer.py |
| 1(b) | Extract 6-category risk feature set | C1 | features.py |
| 1(c) | Apply calibrated gradient-boosting classifier | C1 | model.py, calibration.py |
| 1(d) | Compare to F-beta optimised threshold | C1 | inference.py |
| 1(e) | Counterparty-specific risk-adjusted cost | C2 | model.py, fee.py |
| 1(f) | Generate liquidity provision offer | C7 | agent.py |
| 1(g) | Transmit within commercially useful latency | Pipeline | pipeline.py (≤94ms SLO) |
| 1(h) | Auto-collect repayment on settlement | C3 | repayment_loop.py |

### Dependent Claims
| Claim | Description | Component | Key File |
|-------|-------------|-----------|----------|
| D1 | ISO 20022 pacs.002 parsing | C5 | event_normalizer.py |
| D3 | F-beta threshold (β=2) | C1 | training.py |
| D4 | Tier 1 PD: Merton/KMV structural | C2 | baseline.py |
| D5 | Tier 2 PD: Damodaran proxy | C2 | baseline.py |
| D6 | Tier 3 PD: Altman Z'-score | C2 | baseline.py |
| D7 | Bridge loan secured by receivable assignment | C3 | repayment_loop.py |
| D11 | Settlement via SWIFT gpi UETR | C3 | uetr_mapping.py |

### System Architecture Claims
| Claim | Description | Components |
|-------|-------------|------------|
| 2(ii) | Failure prediction component | C1 |
| 2(iii) | Counterparty risk assessment | C2 |
| 2(iv) | Liquidity pricing component | C2 |
| 2(v) | Liquidity execution component | C7 |
| 2(vi) | Settlement monitoring component | C3 |
| 5(t-x) | Settlement-confirmation auto-repayment loop | C3 |

## Verification Protocol
1. For each claim, verify the corresponding code implements the described behavior
2. Check that canonical constants match the patent specification
3. Verify state machine transitions match the patent's lifecycle description
4. Ensure audit trail captures claim provenance in decision logs
5. Flag any implementation gaps or deviations from spec

## Key Differentiation from Prior Art
- JPMorgan US7089207B1 covers ONLY listed companies with observable equity (Tier 1)
- LIP's Tier 2 (Damodaran) and Tier 3 (Altman Z') handle private/data-sparse counterparties
- This is the core technical contribution — verify Tier 2 and Tier 3 are fully implemented

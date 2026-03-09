# C6 AML Velocity — Sanctions Data

## Source Lists (all public domain / no license fee)

| List | Source | Format | Cadence |
|------|--------|--------|---------|
| **OFAC SDN** | US Treasury — https://sanctionslist.ofac.treas.gov/ | CSV | Daily updates |
| **UN Consolidated** | UN Security Council — https://scsanctions.un.org/ | XML | Irregular |
| **EU CFSP** | EEAS — https://data.europa.eu/ | XML | As updated |

All three lists are published by government bodies as open government data
with no commercial license restrictions.

## How to Refresh

**Manual (one-time or test):**
```bash
python -m lip.c6_aml_velocity.sanctions_loader \
    --output lip/c6_aml_velocity/data/sanctions.json
```

**Automated:** `.github/workflows/update-sanctions.yml` runs weekly and
commits an updated `sanctions.json` if the downloaded data has changed.

## Runtime Wiring

`AMLChecker` reads `LIP_SANCTIONS_PATH` env var (default:
`/app/lip/c6_aml_velocity/data/sanctions.json`) and passes it to
`SanctionsScreener(lists_path=...)`.

The C6 container image copies this directory at build time. The container
itself remains **zero-outbound** at runtime — all list data is baked in.

## Fuzzy Matching

`SanctionsScreener` uses Jaccard similarity (token overlap) with a 0.80
confidence threshold. This catches common name variations and transliterations
without requiring exact matches.

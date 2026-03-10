# LIP Security Audit

Run comprehensive security checks across the LIP platform.

## Audit Scope

### C6 AML/Sanctions
- Verify sanctions list loading (OFAC, EU consolidated)
- Check velocity limits: $1M per entity per 24hr, 100 txn cap
- Validate beneficiary concentration threshold (>80% triggers alert)
- Verify cross-licensee salt rotation (365d cycle, 30d overlap)
- Ensure SHA-256 hashing (NOT MD5) for entity pseudonymization

### C8 License Manager
- Verify HMAC-SHA256 token generation and validation
- Check boot validator prevents unlicensed operation
- Validate license expiry enforcement
- Test token tampering detection

### Common Encryption
- Verify AES-256-GCM for data at rest
- Check key derivation (PBKDF2 or scrypt)
- Validate IV/nonce uniqueness

### Infrastructure
- Review K8s network policies (lip/infrastructure/kubernetes/network-policies.yaml)
- Check secrets management (no plaintext secrets in manifests)
- Verify Docker images use non-root users

### Regulatory
- DORA compliance: operational resilience requirements
- EU AI Act: model transparency and explainability (C1 SHAP)
- SR 11-7: model risk management governance

## Execution Protocol
1. Read and audit each security-critical file
2. Run existing security tests: `PYTHONPATH=. python -m pytest lip/tests/test_c6_aml.py lip/tests/test_c8_license.py -v`
3. Check for hardcoded secrets: grep for API keys, tokens, passwords
4. Review .gitignore for sensitive file exclusions
5. Report findings with severity (CRITICAL / HIGH / MEDIUM / LOW)

## Rules
- NEVER log or print encryption keys, tokens, or salts
- NEVER commit sanctions corpus files
- Salt rotation constants require CIPHER sign-off to change
- Decision logs must be retained for 7 years (DECISION_LOG_RETENTION_YEARS = 7)

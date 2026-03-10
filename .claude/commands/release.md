# LIP Release Management

Prepare and cut a new release of the LIP platform.

## Pre-release Checklist
1. All CI green: `gh run list --limit 3`
2. All tests pass: `/test`
3. Lint clean: `/lint`
4. No open critical issues: `gh issue list --label critical`
5. Gap analysis reviewed: `/gap`
6. Security audit passed: `/security`
7. Version bumped in `lip/pyproject.toml`
8. CHANGELOG updated

## Version Strategy
- **Major** (X.0.0): Breaking API changes, new patent claims
- **Minor** (1.X.0): New components, new features, model improvements
- **Patch** (1.0.X): Bug fixes, performance improvements, dependency updates

## Release Process
1. Create release branch: `git checkout -b release/vX.Y.Z`
2. Bump version in `lip/pyproject.toml`
3. Run full validation: `/test` + `/lint` + `/security`
4. Create PR: `gh pr create --title "Release vX.Y.Z" --body "..."`
5. After merge: `git tag vX.Y.Z && git push origin vX.Y.Z`
6. Create GitHub release: `gh release create vX.Y.Z --title "LIP vX.Y.Z" --notes "..."`

## Artifact Checklist
- [ ] Model artifacts (C1, C2, C4, C6) trained and validated
- [ ] Docker images built and tagged
- [ ] Helm chart version updated
- [ ] License tokens generated for target licensees
- [ ] Deployment runbook updated

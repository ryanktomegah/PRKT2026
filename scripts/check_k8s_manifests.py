#!/usr/bin/env python3
"""
check_k8s_manifests.py — Validate LIP K8s manifests and Helm chart.

Checks:
  1. 7 Dockerfiles map to 7 K8s deployments
  2. EXPOSE ports in Dockerfiles match containerPort in deployments
  3. helm template renders without errors (per env)
  4. No hardcoded secrets in manifests
  5. No :latest image tags in prod values

Usage:
    python scripts/check_k8s_manifests.py
    python scripts/check_k8s_manifests.py --env dev
    python scripts/check_k8s_manifests.py --env staging
    python scripts/check_k8s_manifests.py --env prod

Exit code: 0 = all checks pass, 1 = any check fails.
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
K8S_DIR = ROOT / "lip" / "infrastructure" / "kubernetes"
DOCKER_DIR = ROOT / "lip" / "infrastructure" / "docker"
HELM_CHART = ROOT / "lip" / "infrastructure" / "helm" / "lip"

COMPONENTS = ["c1", "c2", "c3", "c4", "c5", "c6", "c7"]


def check_dockerfiles_vs_deployments(failures):
    """1. Verify 7 Dockerfiles ↔ 7 K8s deployments exist."""
    for c in COMPONENTS:
        df = DOCKER_DIR / f"Dockerfile.{c}"
        dep = K8S_DIR / f"{c}-deployment.yaml"
        if df.exists():
            print(f"  [PASS] Dockerfile.{c} exists")
        else:
            failures.append(f"Missing: {df}")
            print(f"  [FAIL] Missing Dockerfile.{c}")
        if dep.exists():
            print(f"  [PASS] {c}-deployment.yaml exists")
        else:
            failures.append(f"Missing: {dep}")
            print(f"  [FAIL] Missing {c}-deployment.yaml")


def check_port_consistency(failures):
    """2. Cross-check EXPOSE ports in Dockerfiles vs containerPort in deployments.

    Note: c5 uses a split-image architecture (Python worker Dockerfile + vanilla
    Flink/Kafka images in the K8s manifest). Port consistency for c5 is a warning,
    not a failure, since the EXPOSE port (Flink TaskManager 6122) is for the worker
    container while the deployment covers the full Flink cluster.
    """
    # Components where a split-image architecture means Dockerfile port may not
    # appear in the deployment (worker Dockerfile ≠ deployment base image).
    SPLIT_IMAGE = {"c5"}

    for c in COMPONENTS:
        df_path = DOCKER_DIR / f"Dockerfile.{c}"
        dep_path = K8S_DIR / f"{c}-deployment.yaml"
        if not df_path.exists() or not dep_path.exists():
            continue

        df_text = df_path.read_text()
        dep_text = dep_path.read_text()

        # Extract EXPOSE ports from Dockerfile
        expose_ports = set(re.findall(r"^EXPOSE\s+(\d+)", df_text, re.MULTILINE))
        # Extract containerPort from K8s deployment
        container_ports = set(re.findall(r"containerPort:\s*(\d+)", dep_text))

        if expose_ports and container_ports:
            overlap = expose_ports & container_ports
            if overlap:
                print(f"  [PASS] {c}: ports {sorted(overlap)} consistent between Dockerfile and deployment")
            elif c in SPLIT_IMAGE:
                print(
                    f"  [WARN] {c}: split-image architecture — "
                    f"Dockerfile EXPOSE={sorted(expose_ports)} (worker), "
                    f"deployment containerPort={sorted(container_ports)} (cluster). Expected."
                )
            else:
                failures.append(
                    f"Port mismatch {c}: Dockerfile EXPOSE={sorted(expose_ports)} "
                    f"vs deployment containerPort={sorted(container_ports)}"
                )
                print(
                    f"  [FAIL] Port mismatch {c}: Dockerfile EXPOSE={sorted(expose_ports)} "
                    f"vs deployment containerPort={sorted(container_ports)}"
                )
        else:
            print(f"  [SKIP] {c}: could not extract ports for comparison")


def check_no_hardcoded_secrets(failures):
    """4. No hardcoded secrets or API keys in manifests."""
    secret_patterns = [
        r"password:\s*['\"]?\S{8,}",     # password: some_actual_value
        r"ghp_[A-Za-z0-9]{36}",          # GitHub token
        r"AIza[0-9A-Za-z_\-]{35}",       # GCP API key
        r"[Aa][Ww][Ss].{0,30}['\"][0-9a-zA-Z/+]{40}['\"]",  # AWS secret
    ]
    yaml_files = list(K8S_DIR.glob("*.yaml")) + list(HELM_CHART.glob("**/*.yaml"))
    found_secrets = []
    for f in yaml_files:
        text = f.read_text()
        for pattern in secret_patterns:
            if re.search(pattern, text):
                found_secrets.append(f"{f.name}: matches pattern {pattern[:30]!r}")

    if found_secrets:
        for s in found_secrets:
            failures.append(f"Possible hardcoded secret: {s}")
            print(f"  [FAIL] {s}")
    else:
        print(f"  [PASS] No hardcoded secrets found in {len(yaml_files)} manifest files")


def check_no_latest_in_prod(failures):
    """5. No :latest image tags in prod values."""
    prod_values = HELM_CHART / "values-prod.yaml"
    if not prod_values.exists():
        print("  [SKIP] values-prod.yaml not found")
        return

    text = prod_values.read_text()
    # Allow the comment that says "Never use :latest" but not an actual tag: latest assignment
    latest_lines = [
        line for line in text.splitlines()
        if re.search(r"^\s+tag:\s*latest", line) and not line.strip().startswith("#")
    ]
    if latest_lines:
        failures.append(f"values-prod.yaml uses tag: latest — must be explicit semver tag")
        print(f"  [FAIL] values-prod.yaml uses tag: latest")
    else:
        print("  [PASS] values-prod.yaml does not hardcode tag: latest")


def check_helm_template(env, failures):
    """3. helm template renders without errors."""
    if not shutil.which("helm"):
        print("  [SKIP] helm not installed — skipping template render check")
        return

    values_file = HELM_CHART / f"values-{env}.yaml"
    if not values_file.exists():
        print(f"  [SKIP] values-{env}.yaml not found — skipping helm template check")
        return

    cmd = [
        "helm", "template", "lip", str(HELM_CHART),
        "-f", str(values_file),
        "--set", "image.tag=sha-test1234",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  [PASS] helm template renders cleanly for env={env}")
    else:
        failures.append(f"helm template failed for env={env}: {result.stderr[:200]}")
        print(f"  [FAIL] helm template error for env={env}:")
        print(f"         {result.stderr[:300]}")


def main():
    parser = argparse.ArgumentParser(description="Validate LIP K8s manifests")
    parser.add_argument("--env", choices=["dev", "staging", "prod", "all"], default="all")
    args = parser.parse_args()

    failures = []

    print("=== Dockerfile ↔ Deployment coverage ===")
    check_dockerfiles_vs_deployments(failures)

    print("\n=== Port consistency ===")
    check_port_consistency(failures)

    print("\n=== Secret hygiene ===")
    check_no_hardcoded_secrets(failures)

    print("\n=== Prod :latest guard ===")
    check_no_latest_in_prod(failures)

    envs = ["dev", "staging", "prod"] if args.env == "all" else [args.env]
    print(f"\n=== Helm template render ({', '.join(envs)}) ===")
    for env in envs:
        check_helm_template(env, failures)

    print()
    if failures:
        print(f"FAIL — {len(failures)} check(s) failed:")
        for f in failures:
            print(f"  ✗ {f}")
        sys.exit(1)
    else:
        print("PASS — all K8s manifest checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()

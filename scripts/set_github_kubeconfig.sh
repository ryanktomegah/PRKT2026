#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: scripts/set_github_kubeconfig.sh <kubeconfig-path>" >&2
  exit 1
fi

kubeconfig_path="$1"

if [[ ! -f "${kubeconfig_path}" ]]; then
  echo "Kubeconfig not found: ${kubeconfig_path}" >&2
  exit 1
fi

chmod 600 "${kubeconfig_path}"
gh secret set KUBECONFIG -R ryanktomegah/PRKT2026 < "${kubeconfig_path}"
echo "Updated GitHub secret KUBECONFIG for ryanktomegah/PRKT2026"

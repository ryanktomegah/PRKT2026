#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/make_kubeconfig.sh [output-path]

Required environment variables:
  KUBE_SERVER         Kubernetes API server URL, e.g. https://1.2.3.4:443
  KUBE_TOKEN          Bearer token for the service account / user

Optional environment variables:
  KUBE_CLUSTER_NAME   Cluster name in kubeconfig (default: lip-staging)
  KUBE_USER_NAME      User name in kubeconfig (default: lip-deployer)
  KUBE_CONTEXT_NAME   Context name in kubeconfig (default: lip-staging)
  KUBE_NAMESPACE      Default namespace (default: lip-staging)
  KUBE_CA_DATA_B64    Base64-encoded cluster CA certificate data
  KUBE_CA_FILE        Path to PEM CA certificate file (alternative to KUBE_CA_DATA_B64)
  KUBECONFIG_OUTPUT   Output path if not provided as argv[1]

Examples:
  export KUBE_SERVER="https://34.123.45.67"
  export KUBE_TOKEN="..."
  export KUBE_CA_DATA_B64="$(base64 < ca.crt | tr -d '\n')"
  scripts/make_kubeconfig.sh .secrets/staging.kubeconfig

  export KUBE_CA_FILE=/path/to/ca.crt
  scripts/make_kubeconfig.sh
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

: "${KUBE_SERVER:?KUBE_SERVER is required}"
: "${KUBE_TOKEN:?KUBE_TOKEN is required}"

if [[ -z "${KUBE_CA_DATA_B64:-}" && -z "${KUBE_CA_FILE:-}" ]]; then
  echo "Either KUBE_CA_DATA_B64 or KUBE_CA_FILE is required." >&2
  exit 1
fi

if [[ -n "${KUBE_CA_FILE:-}" && ! -f "${KUBE_CA_FILE}" ]]; then
  echo "KUBE_CA_FILE does not exist: ${KUBE_CA_FILE}" >&2
  exit 1
fi

if [[ -n "${KUBE_CA_FILE:-}" ]]; then
  if command -v base64 >/dev/null 2>&1; then
    KUBE_CA_DATA_B64="$(base64 < "${KUBE_CA_FILE}" | tr -d '\n')"
  else
    echo "base64 command not found; provide KUBE_CA_DATA_B64 instead." >&2
    exit 1
  fi
fi

cluster_name="${KUBE_CLUSTER_NAME:-lip-staging}"
user_name="${KUBE_USER_NAME:-lip-deployer}"
context_name="${KUBE_CONTEXT_NAME:-lip-staging}"
namespace="${KUBE_NAMESPACE:-lip-staging}"
output_path="${1:-${KUBECONFIG_OUTPUT:-.secrets/staging.kubeconfig}}"
output_dir="$(dirname "${output_path}")"

mkdir -p "${output_dir}"
umask 077

cat > "${output_path}" <<EOF
apiVersion: v1
kind: Config
clusters:
  - name: ${cluster_name}
    cluster:
      server: ${KUBE_SERVER}
      certificate-authority-data: ${KUBE_CA_DATA_B64}
users:
  - name: ${user_name}
    user:
      token: ${KUBE_TOKEN}
contexts:
  - name: ${context_name}
    context:
      cluster: ${cluster_name}
      user: ${user_name}
      namespace: ${namespace}
current-context: ${context_name}
EOF

chmod 600 "${output_path}"

echo "Wrote kubeconfig to ${output_path}"
echo
echo "Next steps:"
echo "  export KUBECONFIG=${output_path}"
echo "  gh secret set KUBECONFIG -R ryanktomegah/PRKT2026 < ${output_path}"

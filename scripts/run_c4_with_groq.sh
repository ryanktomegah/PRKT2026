#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${LIP_ENV_FILE:-${REPO_ROOT}/.env.local}"

usage() {
  cat <<'EOF'
Usage:
  scripts/run_c4_with_groq.sh doctor
  scripts/run_c4_with_groq.sh test-unit
  scripts/run_c4_with_groq.sh test-live [pytest args...]
  scripts/run_c4_with_groq.sh eval-negation [script args...]
  scripts/run_c4_with_groq.sh cmd -- <command> [args...]

Commands:
  doctor         Verify Groq env wiring and secret file presence.
  test-unit      Run local C4 backend/unit coverage checks.
  test-live      Run Groq-backed live integration tests.
  eval-negation  Run the 500-case Groq negation evaluation script.
  cmd -- ...     Run an arbitrary command with .env.local loaded.

Environment:
  LIP_ENV_FILE   Override the env file to source. Default: .env.local
EOF
}

load_env() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Missing env file: ${ENV_FILE}" >&2
    echo "Create .env.local with LIP_C4_BACKEND=groq and GROQ_API_KEY_FILE." >&2
    exit 1
  fi

  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a

  cd "${REPO_ROOT}"
  export PYTHONPATH="${PYTHONPATH:-.}"
}

require_groq() {
  if [[ "${LIP_C4_BACKEND:-}" != "groq" ]]; then
    echo "Expected LIP_C4_BACKEND=groq, got '${LIP_C4_BACKEND:-unset}'." >&2
    exit 1
  fi

  if [[ -n "${GROQ_API_KEY_FILE:-}" ]]; then
    if [[ ! -f "${GROQ_API_KEY_FILE}" ]]; then
      echo "GROQ_API_KEY_FILE does not exist: ${GROQ_API_KEY_FILE}" >&2
      exit 1
    fi
    if [[ ! -s "${GROQ_API_KEY_FILE}" ]]; then
      echo "GROQ_API_KEY_FILE is empty: ${GROQ_API_KEY_FILE}" >&2
      exit 1
    fi
    return 0
  fi

  if [[ -z "${GROQ_API_KEY:-}" ]]; then
    echo "Set GROQ_API_KEY or GROQ_API_KEY_FILE before running Groq-backed C4." >&2
    exit 1
  fi
}

main() {
  local command="${1:-doctor}"
  if [[ $# -gt 0 ]]; then
    shift
  fi

  case "${command}" in
    doctor)
      load_env
      require_groq
      echo "C4 backend: ${LIP_C4_BACKEND}"
      echo "C4 model: ${LIP_C4_MODEL:-qwen/qwen3-32b}"
      if [[ -n "${GROQ_API_KEY_FILE:-}" ]]; then
        echo "Groq secret: file-backed (${GROQ_API_KEY_FILE})"
      else
        echo "Groq secret: env-backed (GROQ_API_KEY)"
      fi
      echo "PYTHONPATH: ${PYTHONPATH}"
      ;;
    test-unit)
      load_env
      require_groq
      python -m pytest \
        lip/tests/test_c4_backends.py \
        lip/tests/test_c3_c4_c5_coverage.py \
        -q \
        "$@"
      ;;
    test-live)
      load_env
      require_groq
      python -m pytest lip/tests/test_c4_llm_integration.py -q -rs "$@"
      ;;
    eval-negation)
      load_env
      require_groq
      python scripts/evaluate_c4_on_negation_corpus.py "$@"
      ;;
    cmd)
      load_env
      require_groq
      if [[ "${1:-}" == "--" ]]; then
        shift
      fi
      if [[ $# -eq 0 ]]; then
        echo "cmd requires a command after --" >&2
        exit 1
      fi
      exec "$@"
      ;;
    -h|--help|help)
      usage
      ;;
    *)
      echo "Unknown command: ${command}" >&2
      usage >&2
      exit 1
      ;;
  esac
}

main "$@"

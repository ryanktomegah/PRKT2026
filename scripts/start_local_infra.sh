#!/usr/bin/env bash
# start_local_infra.sh — Launch LIP local prototype infrastructure
#
# Starts Redpanda (Kafka) + Redis Standalone via Docker Compose, then waits
# for both services to be healthy and creates all Kafka topics.
#
# Usage:
#   ./scripts/start_local_infra.sh           # start
#   ./scripts/start_local_infra.sh --down    # stop and remove
#   ./scripts/start_local_infra.sh --status  # show running containers
#
# Environment variables set by this script (for your shell session):
#   LIP_KAFKA_BOOTSTRAP_SERVERS=localhost:9092
#   LIP_REDIS_HOST=localhost
#   LIP_REDIS_PORT=6379
#   LIP_REDIS_SSL=false
#   LIP_REDIS_CLUSTER_MODE=false
#
# PHASE-2-STUB: In production, set these env vars to bank Kafka/Redis endpoints.
# No code changes required — only env var updates.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.yml"

# ── Subcommand handling ────────────────────────────────────────────────────────
case "${1:-}" in
  --down)
    echo "Stopping LIP local infrastructure..."
    docker compose -f "${COMPOSE_FILE}" down
    echo "Done."
    exit 0
    ;;
  --status)
    docker compose -f "${COMPOSE_FILE}" ps
    exit 0
    ;;
  --logs)
    docker compose -f "${COMPOSE_FILE}" logs -f
    exit 0
    ;;
  "")
    # default: start
    ;;
  *)
    echo "Usage: $0 [--down | --status | --logs]" >&2
    exit 1
    ;;
esac

# ── Pre-flight checks ──────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo "ERROR: Docker not found. Install Docker Desktop: https://docs.docker.com/get-docker/" >&2
  exit 1
fi

if ! docker info &>/dev/null 2>&1; then
  echo "ERROR: Docker daemon is not running. Start Docker Desktop and retry." >&2
  exit 1
fi

# ── Start services ─────────────────────────────────────────────────────────────
echo "Starting LIP local infrastructure (Redpanda + Redis)..."
docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans

# ── Wait for health ────────────────────────────────────────────────────────────
echo "Waiting for Redpanda to be healthy..."
MAX_WAIT=120
ELAPSED=0
until docker compose -f "${COMPOSE_FILE}" ps redpanda | grep -q "healthy"; do
  if [[ ${ELAPSED} -ge ${MAX_WAIT} ]]; then
    echo "ERROR: Redpanda did not become healthy within ${MAX_WAIT}s" >&2
    docker compose -f "${COMPOSE_FILE}" logs redpanda | tail -20
    exit 1
  fi
  sleep 3
  ELAPSED=$((ELAPSED + 3))
  echo "  ... waiting (${ELAPSED}s / ${MAX_WAIT}s)"
done
echo "Redpanda is healthy."

echo "Waiting for Redis to be healthy..."
ELAPSED=0
until docker compose -f "${COMPOSE_FILE}" ps redis | grep -q "healthy"; do
  if [[ ${ELAPSED} -ge 30 ]]; then
    echo "ERROR: Redis did not become healthy within 30s" >&2
    exit 1
  fi
  sleep 2
  ELAPSED=$((ELAPSED + 2))
done
echo "Redis is healthy."

# ── Topic verification ─────────────────────────────────────────────────────────
echo ""
echo "LIP Kafka topics:"
docker exec lip-redpanda rpk topic list --brokers localhost:9092 2>/dev/null || true

# ── Environment export ─────────────────────────────────────────────────────────
echo ""
echo "Infrastructure is ready. Add these exports to your shell (or .env file):"
echo ""
echo "  export LIP_KAFKA_BOOTSTRAP_SERVERS=localhost:9092"
echo "  export LIP_REDIS_HOST=localhost"
echo "  export LIP_REDIS_PORT=6379"
echo "  export LIP_REDIS_SSL=false"
echo "  export LIP_REDIS_CLUSTER_MODE=false"
echo ""
echo "Run tests:"
echo "  PYTHONPATH=. LIP_KAFKA_BOOTSTRAP_SERVERS=localhost:9092 \\"
echo "  LIP_REDIS_HOST=localhost LIP_REDIS_SSL=false \\"
echo "  python -m pytest lip/tests/ --ignore=lip/tests/test_e2e_pipeline.py -q"

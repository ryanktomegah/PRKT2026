#!/usr/bin/env bash
# init_topics.sh — Create all LIP Kafka topics on a running Redpanda/Kafka cluster
#
# Run this if topics need to be recreated (e.g. after `docker compose down -v`).
# Idempotent: existing topics are skipped (`|| true` on each create command).
#
# Usage:
#   ./scripts/init_topics.sh                              # default localhost:9092
#   ./scripts/init_topics.sh --brokers mybroker:9092      # custom broker
#   ./scripts/init_topics.sh --brokers mybroker:9092 --replicas 3  # production
#
# Topic definitions mirror kafka_config.py TOPIC_DEFINITIONS exactly.
# Update both files together if partition counts change (QUANT sign-off required
# for DECISION_LOG retention changes).

set -euo pipefail

# ── Argument parsing ───────────────────────────────────────────────────────────
BROKERS="localhost:9092"
REPLICAS=1   # 1 for Redpanda single-node; 3 for production Kafka

while [[ $# -gt 0 ]]; do
  case "$1" in
    --brokers)   BROKERS="$2";  shift 2 ;;
    --replicas)  REPLICAS="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

# ── Topic creation helper ──────────────────────────────────────────────────────
create_topic() {
  local name="$1"
  local partitions="$2"
  local extra="${3:-}"
  echo "  Creating ${name} (${partitions}p, ${REPLICAS}r)..."
  rpk topic create "${name}" \
    -p "${partitions}" \
    -r "${REPLICAS}" \
    --brokers "${BROKERS}" \
    ${extra} || echo "    (already exists — skipped)"
}

echo "Connecting to Kafka brokers: ${BROKERS}"
echo "Creating LIP topics (replication factor=${REPLICAS})..."
echo ""

# ── Standard topics (7-day retention) ─────────────────────────────────────────
# Mirrors kafka_config.py TOPIC_DEFINITIONS exactly.
SEVEN_DAYS_MS=$(( 7 * 24 * 3600 * 1000 ))

create_topic "lip.payment.events"      24
create_topic "lip.failure.predictions" 12
create_topic "lip.settlement.signals"  24
create_topic "lip.dispute.results"      6
create_topic "lip.velocity.alerts"      6
create_topic "lip.loan.offers"          6
create_topic "lip.repayment.events"     6
create_topic "lip.dead.letter"          6
create_topic "lip.stress.regime"        6

# ── Decision log: 7-year retention (SR 11-7 + EU AI Act Art.17) ───────────────
SEVEN_YEARS_MS=$(( 7 * 365 * 24 * 3600 * 1000 ))
echo "  Creating lip.decision.log (12p, ${REPLICAS}r, 7-year retention)..."
rpk topic create lip.decision.log \
  -p 12 \
  -r "${REPLICAS}" \
  --brokers "${BROKERS}" \
  -c "retention.ms=${SEVEN_YEARS_MS}" || echo "    (already exists — skipped)"

echo ""
echo "Done. Current topic list:"
rpk topic list --brokers "${BROKERS}"

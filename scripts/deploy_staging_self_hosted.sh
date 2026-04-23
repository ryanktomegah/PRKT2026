#!/usr/bin/env bash
set -euo pipefail

namespace="${1:-lip-staging}"
profile="${STAGING_PROFILE:-local-core}"

case "${profile}" in
  local-core|local-full-non-gpu|gpu-full|analytics|streaming-flink)
    ;;
  *)
    echo "Unsupported STAGING_PROFILE: ${profile}" >&2
    exit 1
    ;;
esac

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "${name} is required for profile ${profile}" >&2
    exit 1
  fi
}

bool_flag() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

load_secret_value() {
  local name="$1"
  local path="$2"
  if [[ -z "${!name:-}" && -f "${path}" ]]; then
    export "${name}=$(<"${path}")"
  fi
}

delete_if_present() {
  kubectl -n "${namespace}" delete "$@" --ignore-not-found >/dev/null 2>&1 || true
}

apply_secret() {
  local name="$1"
  shift
  kubectl -n "${namespace}" create secret generic "${name}" "$@" \
    --dry-run=client -o yaml | kubectl apply -f -
}

generate_ephemeral_license() {
  local line=""
  local generated_token=""
  local generated_key=""

  while IFS= read -r line; do
    if [[ -z "${generated_token}" ]]; then
      generated_token="${line}"
    else
      generated_key="${line}"
    fi
  done < <(
    PYTHONPATH=. python - <<'PY'
import json
import secrets
import os
from datetime import date, timedelta

from lip.c8_license_manager.license_token import ALL_COMPONENTS, LicenseToken, sign_token

key = secrets.token_bytes(32)
today = date.today()
licensee_type = os.environ.get("LIP_STAGING_LICENSEE_TYPE", "PROCESSOR")
sub_licensee_bics = [
    bic.strip()
    for bic in os.environ.get(
        "LIP_PROCESSOR_SUB_LICENSEE_BICS",
        "COBADEFF,DEUTDEFF,CHASUS33",
    ).split(",")
    if bic.strip()
]
token = LicenseToken(
    licensee_id="SELF_HOSTED_STAGING",
    issue_date=today.isoformat(),
    expiry_date=(today + timedelta(days=30)).isoformat(),
    max_tps=500,
    aml_dollar_cap_usd=5_000_000,
    aml_count_cap=500,
    min_loan_amount_usd=500_000,
    deployment_phase="LICENSOR",
    licensee_type=licensee_type,
    sub_licensee_bics=sub_licensee_bics if licensee_type == "PROCESSOR" else [],
    annual_minimum_usd=500_000 if licensee_type == "PROCESSOR" else 0,
    performance_premium_pct=0.15 if licensee_type == "PROCESSOR" else 0.0,
    platform_take_rate_pct=0.20 if licensee_type == "PROCESSOR" else 0.0,
    permitted_components=list(ALL_COMPONENTS),
)
signed = sign_token(token, key)
print(json.dumps(signed.to_dict(), separators=(",", ":")))
print(key.hex())
PY
  )
  echo "${generated_token}"
  echo "${generated_key}"
}

deploy_local_infra() {
  delete_if_present job/lip-redpanda-init
  cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lip-redpanda
  namespace: ${namespace}
  labels:
    app: lip-redpanda
    component: infra
spec:
  replicas: 1
  selector:
    matchLabels:
      app: lip-redpanda
  template:
    metadata:
      labels:
        app: lip-redpanda
        component: infra
    spec:
      containers:
        - name: redpanda
          image: redpandadata/redpanda:v24.1.1
          args:
            - redpanda
            - start
            - --overprovisioned
            - --smp=1
            - --memory=512M
            - --reserve-memory=0M
            - --node-id=0
            - --check=false
            - --kafka-addr=PLAINTEXT://0.0.0.0:9092
            - --advertise-kafka-addr=PLAINTEXT://redpanda:9092
            - --pandaproxy-addr=0.0.0.0:8082
            - --advertise-pandaproxy-addr=redpanda:8082
            - --schema-registry-addr=0.0.0.0:8081
            - --rpc-addr=0.0.0.0:33145
            - --advertise-rpc-addr=redpanda:33145
          ports:
            - containerPort: 9092
              name: kafka
          readinessProbe:
            exec:
              command: ["rpk", "cluster", "health"]
            initialDelaySeconds: 15
            periodSeconds: 5
          livenessProbe:
            exec:
              command: ["rpk", "cluster", "health"]
            initialDelaySeconds: 25
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: redpanda
  namespace: ${namespace}
spec:
  selector:
    app: lip-redpanda
  ports:
    - name: kafka
      port: 9092
      targetPort: 9092
  type: ClusterIP
---
apiVersion: batch/v1
kind: Job
metadata:
  name: lip-redpanda-init
  namespace: ${namespace}
spec:
  template:
    metadata:
      labels:
        app: lip-redpanda-init
    spec:
      restartPolicy: OnFailure
      containers:
        - name: init-topics
          image: redpandadata/redpanda:v24.1.1
          command: ["/bin/bash", "-c"]
          args:
            - |
              set -euo pipefail
              topics=(
                lip.payment.events
                lip.failure.predictions
                lip.settlement.signals
                lip.dispute.results
                lip.velocity.alerts
                lip.loan.offers
                lip.repayment.events
                lip.dead.letter
                lip.stress.regime
              )
              for topic in "\${topics[@]}"; do
                rpk topic create "\${topic}" --brokers redpanda:9092 || true
              done
              rpk topic create lip.decision.log --brokers redpanda:9092 || true
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lip-redis
  namespace: ${namespace}
  labels:
    app: lip-redis
    component: infra
spec:
  replicas: 1
  selector:
    matchLabels:
      app: lip-redis
  template:
    metadata:
      labels:
        app: lip-redis
        component: infra
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          command: ["redis-server", "--save", "", "--appendonly", "no", "--loglevel", "warning"]
          ports:
            - containerPort: 6379
              name: redis
          readinessProbe:
            exec:
              command: ["redis-cli", "ping"]
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            exec:
              command: ["redis-cli", "ping"]
            initialDelaySeconds: 10
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: lip-redis
  namespace: ${namespace}
spec:
  selector:
    app: lip-redis
  ports:
    - name: redis
      port: 6379
      targetPort: 6379
  type: ClusterIP
EOF

  kubectl rollout status deployment/lip-redpanda -n "${namespace}" --timeout=5m
  kubectl rollout status deployment/lip-redis -n "${namespace}" --timeout=5m
  kubectl wait --for=condition=complete job/lip-redpanda-init -n "${namespace}" --timeout=5m
}

deploy_c2() {
  cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lip-c2-pd
  namespace: ${namespace}
  labels:
    app: lip-c2-pd
    component: c2-pd-model
spec:
  replicas: 1
  selector:
    matchLabels:
      app: lip-c2-pd
  template:
    metadata:
      labels:
        app: lip-c2-pd
        component: c2-pd-model
    spec:
      containers:
        - name: c2-pd
          image: ${LIP_C2_IMAGE}
          imagePullPolicy: Never
          ports:
            - containerPort: 8081
              name: http
          env:
            - name: LIP_MODEL_HMAC_KEY
              valueFrom:
                secretKeyRef:
                  name: lip-model-artifact-secret
                  key: model_hmac_key
            - name: LIP_C2_MODEL_PATH
              value: /app/artifacts/c2_trained/c2_model.pkl
            - name: LIP_ENFORCE_LICENSE_VALIDATION
              value: "true"
            - name: LIP_LICENSE_TOKEN_JSON
              valueFrom:
                secretKeyRef:
                  name: lip-license-secret
                  key: token_json
            - name: LIP_LICENSE_KEY_HEX
              valueFrom:
                secretKeyRef:
                  name: lip-license-secret
                  key: key_hex
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8081
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8081
            initialDelaySeconds: 10
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: lip-c2-pd
  namespace: ${namespace}
spec:
  selector:
    app: lip-c2-pd
  ports:
    - name: http
      port: 8081
      targetPort: 8081
  type: ClusterIP
EOF
}

deploy_c4() {
  cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lip-c4-dispute
  namespace: ${namespace}
  labels:
    app: lip-c4-dispute
    component: c4-dispute-classifier
spec:
  replicas: 1
  selector:
    matchLabels:
      app: lip-c4-dispute
  template:
    metadata:
      labels:
        app: lip-c4-dispute
        component: c4-dispute-classifier
    spec:
      containers:
        - name: c4-dispute
          image: ${LIP_C4_IMAGE}
          imagePullPolicy: Never
          ports:
            - containerPort: 8080
              name: http
          env:
            - name: LIP_C4_BACKEND
              value: groq
            - name: LIP_C4_MODEL
              value: qwen/qwen3-32b
            - name: LIP_ENFORCE_LICENSE_VALIDATION
              value: "true"
            - name: GROQ_API_KEY
              valueFrom:
                secretKeyRef:
                  name: lip-groq-secret
                  key: api_key
            - name: LIP_LICENSE_TOKEN_JSON
              valueFrom:
                secretKeyRef:
                  name: lip-license-secret
                  key: token_json
            - name: LIP_LICENSE_KEY_HEX
              valueFrom:
                secretKeyRef:
                  name: lip-license-secret
                  key: key_hex
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: lip-c4-dispute
  namespace: ${namespace}
spec:
  selector:
    app: lip-c4-dispute
  ports:
    - name: http
      port: 8080
      targetPort: 8080
  type: ClusterIP
EOF
}

deploy_c6() {
  local redis_url_env=""
  if bool_flag "${DEPLOY_LOCAL_INFRA:-false}"; then
    redis_url_env=$'
            - name: REDIS_URL
              value: redis://lip-redis:6379/0'
  fi
  cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lip-c6-aml
  namespace: ${namespace}
  labels:
    app: lip-c6-aml
    component: c6-aml-velocity
spec:
  replicas: 1
  selector:
    matchLabels:
      app: lip-c6-aml
  template:
    metadata:
      labels:
        app: lip-c6-aml
        component: c6-aml-velocity
    spec:
      containers:
        - name: c6-aml
          image: ${LIP_C6_IMAGE}
          imagePullPolicy: Never
          ports:
            - containerPort: 8082
              name: http
          env:${redis_url_env}
            - name: LIP_AML_SALT
              valueFrom:
                secretKeyRef:
                  name: lip-aml-secret
                  key: current_salt
            - name: LIP_ENFORCE_LICENSE_VALIDATION
              value: "true"
            - name: LIP_LICENSE_TOKEN_JSON
              valueFrom:
                secretKeyRef:
                  name: lip-license-secret
                  key: token_json
            - name: LIP_LICENSE_KEY_HEX
              valueFrom:
                secretKeyRef:
                  name: lip-license-secret
                  key: key_hex
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8082
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8082
            initialDelaySeconds: 10
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: lip-c6-aml
  namespace: ${namespace}
spec:
  selector:
    app: lip-c6-aml
  ports:
    - name: http
      port: 8082
      targetPort: 8082
  type: ClusterIP
EOF
}

deploy_api() {
  local redis_url_env=""
  if bool_flag "${DEPLOY_LOCAL_INFRA:-false}"; then
    redis_url_env=$'
            - name: REDIS_URL
              value: redis://lip-redis:6379/0'
  fi
  cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lip-api
  namespace: ${namespace}
  labels:
    app: lip-api
    component: c7-api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: lip-api
  template:
    metadata:
      labels:
        app: lip-api
        component: c7-api
    spec:
      containers:
        - name: api
          image: ${LIP_API_IMAGE}
          imagePullPolicy: Never
          ports:
            - containerPort: 8080
              name: http
          env:${redis_url_env}
            - name: LIP_MODEL_HMAC_KEY
              valueFrom:
                secretKeyRef:
                  name: lip-model-artifact-secret
                  key: model_hmac_key
            - name: LIP_API_HMAC_KEY
              valueFrom:
                secretKeyRef:
                  name: lip-api-auth-secret
                  key: hmac_key
            - name: GROQ_API_KEY
              valueFrom:
                secretKeyRef:
                  name: lip-groq-secret
                  key: api_key
            - name: LIP_C4_BACKEND
              value: groq
            - name: LIP_C4_MODEL
              value: qwen/qwen3-32b
            - name: LIP_C1_MODEL_DIR
              value: /app/artifacts/c1_trained
            - name: LIP_C2_MODEL_PATH
              value: /app/artifacts/c2_trained/c2_model.pkl
            - name: LIP_API_ENABLE_REAL_PIPELINE
              value: "true"
            - name: LIP_ENFORCE_LICENSE_VALIDATION
              value: "true"
            - name: LIP_LICENSE_TOKEN_JSON
              valueFrom:
                secretKeyRef:
                  name: lip-license-secret
                  key: token_json
            - name: LIP_LICENSE_KEY_HEX
              valueFrom:
                secretKeyRef:
                  name: lip-license-secret
                  key: key_hex
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: lip-api
  namespace: ${namespace}
spec:
  selector:
    app: lip-api
  ports:
    - name: http
      port: 8080
      targetPort: 8080
  type: ClusterIP
EOF
}

deploy_c3() {
  cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lip-c3-repayment
  namespace: ${namespace}
  labels:
    app: lip-c3-repayment
    component: c3-repayment-engine
spec:
  replicas: 1
  selector:
    matchLabels:
      app: lip-c3-repayment
  template:
    metadata:
      labels:
        app: lip-c3-repayment
        component: c3-repayment-engine
    spec:
      containers:
        - name: c3-repayment
          image: ${LIP_C3_IMAGE}
          imagePullPolicy: Never
          ports:
            - containerPort: 8083
              name: http
          env:
            - name: REDIS_URL
              value: redis://lip-redis:6379/0
            - name: LIP_ENFORCE_LICENSE_VALIDATION
              value: "true"
            - name: LIP_LICENSE_TOKEN_JSON
              valueFrom:
                secretKeyRef:
                  name: lip-license-secret
                  key: token_json
            - name: LIP_LICENSE_KEY_HEX
              valueFrom:
                secretKeyRef:
                  name: lip-license-secret
                  key: key_hex
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8083
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8083
            initialDelaySeconds: 10
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: lip-c3-repayment
  namespace: ${namespace}
spec:
  selector:
    app: lip-c3-repayment
  ports:
    - name: http
      port: 8083
      targetPort: 8083
  type: ClusterIP
EOF
}

deploy_c5_go() {
  cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lip-c5-go
  namespace: ${namespace}
  labels:
    app: lip-c5-go
    component: c5-go-consumer
spec:
  replicas: 1
  selector:
    matchLabels:
      app: lip-c5-go
  template:
    metadata:
      labels:
        app: lip-c5-go
        component: c5-go-consumer
    spec:
      containers:
        - name: c5-go
          image: ${LIP_C5_GO_IMAGE}
          imagePullPolicy: Never
          ports:
            - containerPort: 9090
              name: metrics
          env:
            - name: KAFKA_BOOTSTRAP_SERVERS
              value: redpanda:9092
            - name: KAFKA_SECURITY_PROTOCOL
              value: PLAINTEXT
            - name: KAFKA_GROUP_ID
              value: lip-c5-go-staging
            - name: REDIS_ADDR
              value: lip-redis:6379
            - name: DRY_RUN
              value: "true"
            - name: NUM_WORKERS
              value: "2"
          readinessProbe:
            httpGet:
              path: /healthz
              port: 9090
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /healthz
              port: 9090
            initialDelaySeconds: 10
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: lip-c5-go
  namespace: ${namespace}
spec:
  selector:
    app: lip-c5-go
  ports:
    - name: metrics
      port: 9090
      targetPort: 9090
  type: ClusterIP
EOF
}

deploy_c5_python() {
  cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lip-c5-python
  namespace: ${namespace}
  labels:
    app: lip-c5-python
    component: c5-streaming-python
spec:
  replicas: 1
  selector:
    matchLabels:
      app: lip-c5-python
  template:
    metadata:
      labels:
        app: lip-c5-python
        component: c5-streaming-python
    spec:
      containers:
        - name: c5-python
          image: ${LIP_C5_IMAGE}
          imagePullPolicy: Never
          command: ["python3.11", "-m", "lip.c5_streaming.kafka_worker", "--group-id", "lip-c5-python-staging", "--dry-run"]
          env:
            - name: KAFKA_BOOTSTRAP_SERVERS
              value: redpanda:9092
            - name: PYTHONPATH
              value: /app
EOF
}

deploy_c1() {
  cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lip-c1
  namespace: ${namespace}
  labels:
    app: lip-c1
    component: c1-failure-classifier
spec:
  replicas: 1
  selector:
    matchLabels:
      app: lip-c1
  template:
    metadata:
      labels:
        app: lip-c1
        component: c1-failure-classifier
    spec:
      containers:
        - name: c1
          image: ${LIP_C1_IMAGE}
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8000
              name: http
          volumeMounts:
            - name: model-repo
              mountPath: /models
          env:
            - name: LIP_ENFORCE_LICENSE_VALIDATION
              value: "true"
            - name: LIP_LICENSE_TOKEN_JSON
              valueFrom:
                secretKeyRef:
                  name: lip-license-secret
                  key: token_json
            - name: LIP_LICENSE_KEY_HEX
              valueFrom:
                secretKeyRef:
                  name: lip-license-secret
                  key: key_hex
          readinessProbe:
            httpGet:
              path: /v2/health/ready
              port: 8000
            initialDelaySeconds: 20
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /v2/health/live
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 15
      volumes:
        - name: model-repo
          hostPath:
            path: ${LIP_C1_MODEL_REPO_HOST_PATH}
            type: Directory
---
apiVersion: v1
kind: Service
metadata:
  name: lip-c1
  namespace: ${namespace}
spec:
  selector:
    app: lip-c1
  ports:
    - name: http
      port: 8000
      targetPort: 8000
  type: ClusterIP
EOF
}

deploy_c9_job() {
  delete_if_present job/lip-c9-analytics
  cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: lip-c9-analytics
  namespace: ${namespace}
spec:
  backoffLimit: 1
  template:
    metadata:
      labels:
        app: lip-c9-analytics
        component: c9-settlement-predictor
    spec:
      restartPolicy: Never
      containers:
        - name: c9
          image: ${LIP_API_IMAGE}
          imagePullPolicy: Never
          command: ["python", "-m", "lip.c9_settlement_predictor.job"]
EOF
}

cleanup_profile_resources() {
  case "${profile}" in
    local-core)
      delete_if_present deployment/lip-c3-repayment service/lip-c3-repayment
      delete_if_present deployment/lip-c5-go service/lip-c5-go
      delete_if_present deployment/lip-c5-python
      delete_if_present deployment/lip-c1 service/lip-c1
      delete_if_present deployment/lip-redpanda service/redpanda deployment/lip-redis service/lip-redis
      delete_if_present job/lip-redpanda-init job/lip-c9-analytics
      ;;
    local-full-non-gpu)
      delete_if_present deployment/lip-c5-python
      delete_if_present deployment/lip-c1 service/lip-c1
      delete_if_present job/lip-c9-analytics
      ;;
    gpu-full)
      delete_if_present deployment/lip-c5-python
      delete_if_present job/lip-c9-analytics
      ;;
    analytics)
      delete_if_present deployment/lip-c2-pd service/lip-c2-pd
      delete_if_present deployment/lip-c4-dispute service/lip-c4-dispute
      delete_if_present deployment/lip-c6-aml service/lip-c6-aml
      delete_if_present deployment/lip-api service/lip-api
      delete_if_present deployment/lip-c3-repayment service/lip-c3-repayment
      delete_if_present deployment/lip-c5-go service/lip-c5-go
      delete_if_present deployment/lip-c5-python
      delete_if_present deployment/lip-c1 service/lip-c1
      delete_if_present deployment/lip-redpanda service/redpanda deployment/lip-redis service/lip-redis
      delete_if_present job/lip-redpanda-init
      ;;
    streaming-flink)
      delete_if_present deployment/lip-c2-pd service/lip-c2-pd
      delete_if_present deployment/lip-c4-dispute service/lip-c4-dispute
      delete_if_present deployment/lip-c6-aml service/lip-c6-aml
      delete_if_present deployment/lip-api service/lip-api
      delete_if_present deployment/lip-c3-repayment service/lip-c3-repayment
      delete_if_present deployment/lip-c5-go service/lip-c5-go
      delete_if_present deployment/lip-c1 service/lip-c1
      delete_if_present job/lip-c9-analytics
      ;;
  esac
}

DEPLOY_LOCAL_INFRA=false
case "${profile}" in
  local-full-non-gpu|gpu-full|streaming-flink)
    DEPLOY_LOCAL_INFRA=true
    ;;
esac
export DEPLOY_LOCAL_INFRA

load_secret_value GROQ_API_KEY .secrets/groq_api_key
load_secret_value LIP_MODEL_HMAC_KEY .secrets/c2_model_hmac_key

if bool_flag "${DEPLOY_LOCAL_INFRA}"; then
  require_env LIP_API_IMAGE
fi

case "${profile}" in
  local-core)
    require_env LIP_C2_IMAGE
    require_env LIP_C4_IMAGE
    require_env LIP_C6_IMAGE
    require_env LIP_API_IMAGE
    require_env GROQ_API_KEY
    require_env LIP_MODEL_HMAC_KEY
    ;;
  local-full-non-gpu)
    require_env LIP_C2_IMAGE
    require_env LIP_C3_IMAGE
    require_env LIP_C4_IMAGE
    require_env LIP_C5_GO_IMAGE
    require_env LIP_C6_IMAGE
    require_env LIP_API_IMAGE
    require_env GROQ_API_KEY
    require_env LIP_MODEL_HMAC_KEY
    ;;
  gpu-full)
    require_env LIP_C1_IMAGE
    require_env LIP_C1_MODEL_REPO_HOST_PATH
    require_env LIP_C2_IMAGE
    require_env LIP_C3_IMAGE
    require_env LIP_C4_IMAGE
    require_env LIP_C5_GO_IMAGE
    require_env LIP_C6_IMAGE
    require_env LIP_API_IMAGE
    require_env GROQ_API_KEY
    require_env LIP_MODEL_HMAC_KEY
    ;;
  analytics)
    require_env LIP_API_IMAGE
    ;;
  streaming-flink)
    require_env LIP_C5_IMAGE
    ;;
esac

api_hmac_key="${LIP_API_HMAC_KEY:-}"
if [[ -z "${api_hmac_key}" ]]; then
  api_hmac_key="$(openssl rand -hex 32)"
fi

aml_salt="${LIP_AML_SALT:-}"
if [[ -z "${aml_salt}" ]]; then
  aml_salt="$(openssl rand -hex 16)"
fi

license_token_json="${LIP_LICENSE_TOKEN_JSON:-}"
license_key_hex="${LIP_LICENSE_KEY_HEX:-}"
if [[ "${profile}" != "analytics" && ( -z "${license_token_json}" || -z "${license_key_hex}" ) ]]; then
  license_output="$(generate_ephemeral_license)"
  license_token_json="${license_output%%$'\n'*}"
  license_key_hex="${license_output#*$'\n'}"
  echo "Generated ephemeral self-hosted staging license token."
fi

kubectl get namespace "${namespace}" >/dev/null 2>&1 || kubectl create namespace "${namespace}"

cleanup_profile_resources

if [[ "${profile}" != "analytics" ]]; then
  apply_secret lip-license-secret \
    --from-literal=token_json="${license_token_json}" \
    --from-literal=key_hex="${license_key_hex}"
fi

if [[ "${profile}" == local-core || "${profile}" == local-full-non-gpu || "${profile}" == gpu-full ]]; then
  apply_secret lip-groq-secret --from-literal=api_key="${GROQ_API_KEY}"
  apply_secret lip-api-auth-secret --from-literal=hmac_key="${api_hmac_key}"
  apply_secret lip-aml-secret --from-literal=current_salt="${aml_salt}"
  apply_secret lip-model-artifact-secret --from-literal=model_hmac_key="${LIP_MODEL_HMAC_KEY}"
fi

if bool_flag "${DEPLOY_LOCAL_INFRA}"; then
  deploy_local_infra
fi

case "${profile}" in
  local-core)
    deploy_c2
    deploy_c4
    deploy_c6
    deploy_api
    kubectl rollout status deployment/lip-c2-pd -n "${namespace}" --timeout=5m
    kubectl rollout status deployment/lip-c4-dispute -n "${namespace}" --timeout=5m
    kubectl rollout status deployment/lip-c6-aml -n "${namespace}" --timeout=5m
    kubectl rollout status deployment/lip-api -n "${namespace}" --timeout=5m
    ;;
  local-full-non-gpu)
    deploy_c2
    deploy_c3
    deploy_c4
    deploy_c5_go
    deploy_c6
    deploy_api
    kubectl rollout status deployment/lip-c2-pd -n "${namespace}" --timeout=5m
    kubectl rollout status deployment/lip-c3-repayment -n "${namespace}" --timeout=5m
    kubectl rollout status deployment/lip-c4-dispute -n "${namespace}" --timeout=5m
    kubectl rollout status deployment/lip-c5-go -n "${namespace}" --timeout=5m
    kubectl rollout status deployment/lip-c6-aml -n "${namespace}" --timeout=5m
    kubectl rollout status deployment/lip-api -n "${namespace}" --timeout=5m
    ;;
  gpu-full)
    deploy_c1
    deploy_c2
    deploy_c3
    deploy_c4
    deploy_c5_go
    deploy_c6
    deploy_api
    kubectl rollout status deployment/lip-c1 -n "${namespace}" --timeout=10m
    kubectl rollout status deployment/lip-c2-pd -n "${namespace}" --timeout=5m
    kubectl rollout status deployment/lip-c3-repayment -n "${namespace}" --timeout=5m
    kubectl rollout status deployment/lip-c4-dispute -n "${namespace}" --timeout=5m
    kubectl rollout status deployment/lip-c5-go -n "${namespace}" --timeout=5m
    kubectl rollout status deployment/lip-c6-aml -n "${namespace}" --timeout=5m
    kubectl rollout status deployment/lip-api -n "${namespace}" --timeout=5m
    ;;
  analytics)
    deploy_c9_job
    kubectl wait --for=condition=complete job/lip-c9-analytics -n "${namespace}" --timeout=5m
    ;;
  streaming-flink)
    deploy_c5_python
    kubectl rollout status deployment/lip-c5-python -n "${namespace}" --timeout=5m
    ;;
esac

kubectl get pods -n "${namespace}" -o wide
kubectl get svc -n "${namespace}"

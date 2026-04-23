#!/usr/bin/env bash
set -euo pipefail

namespace="${1:-lip-staging}"

: "${LIP_C4_IMAGE:?LIP_C4_IMAGE is required}"
: "${LIP_API_IMAGE:?LIP_API_IMAGE is required}"
: "${LIP_C6_IMAGE:?LIP_C6_IMAGE is required}"
: "${GROQ_API_KEY:?GROQ_API_KEY is required}"

api_hmac_key="${LIP_API_HMAC_KEY:-}"
if [[ -z "${api_hmac_key}" ]]; then
  api_hmac_key="$(openssl rand -hex 32)"
fi

aml_salt="${LIP_AML_SALT:-}"
if [[ -z "${aml_salt}" ]]; then
  aml_salt="$(openssl rand -hex 16)"
fi

kubectl get namespace "${namespace}" >/dev/null 2>&1 || kubectl create namespace "${namespace}"

kubectl -n "${namespace}" create secret generic lip-groq-secret \
  --from-literal=api_key="${GROQ_API_KEY}" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n "${namespace}" create secret generic lip-api-auth-secret \
  --from-literal=hmac_key="${api_hmac_key}" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n "${namespace}" create secret generic lip-aml-secret \
  --from-literal=current_salt="${aml_salt}" \
  --dry-run=client -o yaml | kubectl apply -f -

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
            - name: LIP_COMPONENT
              value: c4
            - name: LIP_C4_BACKEND
              value: groq
            - name: LIP_C4_MODEL
              value: qwen/qwen3-32b
            - name: GROQ_API_KEY
              valueFrom:
                secretKeyRef:
                  name: lip-groq-secret
                  key: api_key
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
---
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
          env:
            - name: LIP_AML_SALT
              valueFrom:
                secretKeyRef:
                  name: lip-aml-secret
                  key: current_salt
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
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lip-api
  namespace: ${namespace}
  labels:
    app: lip-api
    component: api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: lip-api
  template:
    metadata:
      labels:
        app: lip-api
        component: api
    spec:
      containers:
        - name: api
          image: ${LIP_API_IMAGE}
          imagePullPolicy: Never
          ports:
            - containerPort: 8080
              name: http
          env:
            - name: LIP_API_HMAC_KEY
              valueFrom:
                secretKeyRef:
                  name: lip-api-auth-secret
                  key: hmac_key
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

kubectl rollout status deployment/lip-c4-dispute -n "${namespace}" --timeout=5m
kubectl rollout status deployment/lip-c6-aml -n "${namespace}" --timeout=5m
kubectl rollout status deployment/lip-api -n "${namespace}" --timeout=5m
kubectl get pods -n "${namespace}" -o wide
kubectl get svc -n "${namespace}"

# Automated Liquidity Bridging System

Patent-backed proof-of-concept. Three-component pipeline:
**Payment Failure Prediction** → **CVA Pricing** → **Bridge Loan Execution**

---

## Install

```bash
pip install -r requirements.txt
```

## Start the API

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

The API trains the LightGBM model at startup (~5 seconds). Wait for the log line:
```
[STARTUP] Ready — model trained in X.Xs | threshold=0.XXX | AUC=0.XXX
```
Interactive API docs are available at [http://localhost:8000/docs](http://localhost:8000/docs).

## Start the Dashboard

```bash
streamlit run dashboard.py
```

Opens at [http://localhost:8501](http://localhost:8501). The API must be running first.

---

## Architecture

| Component | File | Patent Claims |
|-----------|------|---------------|
| 1 — Failure Prediction | `failure_prediction_engine.py` | 1(a–d), D1, D3, D9 |
| 2 — CVA Pricing | `cva_pricing_engine.py` | 1(e), D4, D5, D6, D7 |
| 3 — Bridge Execution | `bridge_loan_execution.py` | 1(f–h), 3(m), 5(t–x), D11 |
| 4 — API + Dashboard | `api.py`, `dashboard.py` | D9 (latency enforcement) |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Server liveness + model readiness |
| `/score` | POST | Component 1 — failure probability + SHAP |
| `/price` | POST | Component 2 — CVA assessment + APR |
| `/execute` | POST | Component 3 — bridge loan offer + lifecycle |
| `/catalogue/bics` | GET | Known BIC reference data |
| `/catalogue/corridors` | GET | Supported currency corridors |

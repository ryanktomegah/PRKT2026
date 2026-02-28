# Copilot Instructions for ALBS (Automated Liquidity Bridging System)

This repository contains a patent-backed three-component pipeline for real-time payment failure prediction, CVA pricing, and bridge loan execution, with a dark-themed Next.js dashboard.

## Repository Structure

```
PRKT2026/
├── Project2026 copy/       ← Python FastAPI backend + ML engines
│   ├── api.py              ← FastAPI app (start with uvicorn)
│   ├── failure_prediction_engine.py  ← Component 1: LightGBM-based failure prediction
│   ├── cva_pricing_engine.py         ← Component 2: CVA pricing engine
│   ├── bridge_loan_execution.py      ← Component 3: Bridge loan execution
│   ├── dashboard.py        ← Optional Streamlit dashboard (port 8501)
│   └── requirements.txt
└── frontend/               ← Next.js 14 App Router dashboard
    ├── app/                ← Pages (dashboard, analysis, portfolio, audit)
    ├── components/         ← UI components
    └── lib/                ← API client, Zustand store, utilities
```

## Development Setup

### Backend (Python FastAPI)

```bash
cd "Project2026 copy"
pip install -r requirements.txt
uvicorn api:app --host 0.0.0.0 --port 8000
```

The API will be available at http://localhost:8000. Interactive docs at http://localhost:8000/docs.

### Frontend (Next.js)

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

The frontend will be available at http://localhost:3000.

## Build & Test Commands

### Frontend

- **Lint:** `cd frontend && npm run lint`
- **Build:** `cd frontend && npm run build`
- **Dev server:** `cd frontend && npm run dev`

### Backend

- **Start API:** `cd "Project2026 copy" && uvicorn api:app --host 0.0.0.0 --port 8000`
- **Install deps:** `cd "Project2026 copy" && pip install -r requirements.txt`

## Environment Variables

### Frontend (`frontend/.env.local`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | URL of the FastAPI backend |

### Backend

| Variable | Default | Purpose |
|----------|---------|---------|
| `ALBS_CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated list of allowed browser origins |

## Code Standards

### Frontend (TypeScript / Next.js)

- Use TypeScript for all new files; avoid `any` types where possible.
- Follow Next.js 14 App Router conventions (server vs. client components).
- Use Tailwind CSS for styling; keep the dark theme consistent.
- Use Zustand for global state management and React Query for server state/data fetching.
- Use Radix UI primitives for accessible UI components.
- Run `npm run lint` before committing frontend changes.

### Backend (Python)

- Follow PEP 8 style guidelines.
- Use Pydantic models for request/response validation in FastAPI routes.
- Keep ML logic in the engine files (`failure_prediction_engine.py`, `cva_pricing_engine.py`, `bridge_loan_execution.py`); keep `api.py` focused on routing and HTTP concerns.
- Maintain backward compatibility with Python 3.9+.

## Architecture Notes

| Component | File | Patent Claims |
|-----------|------|---------------|
| 1 — Failure Prediction | `failure_prediction_engine.py` | 1(a–d), D1, D3, D9 |
| 2 — CVA Pricing | `cva_pricing_engine.py` | 1(e), D4, D5, D6, D7 |
| 3 — Bridge Execution | `bridge_loan_execution.py` | 1(f–h), 3(m), 5(t–x), D11 |
| 4 — API | `api.py` | D9 (latency enforcement) |

The three ML/financial components form a sequential pipeline: payment data flows through failure prediction → CVA pricing → bridge loan execution. The FastAPI layer orchestrates this pipeline and enforces latency SLAs.

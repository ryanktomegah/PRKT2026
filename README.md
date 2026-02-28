# Automated Liquidity Bridging System (ALBS)

Patent-backed three-component pipeline for real-time payment failure prediction, CVA pricing, and bridge loan execution — with a dark-themed Next.js dashboard.

---

## How to run it locally (preview in your browser)

You need two terminals open at the same time: one for the Python API backend, one for the Next.js frontend.

### Prerequisites

| Tool | Minimum version | Check with |
|------|----------------|------------|
| Python | 3.9 | `python3 --version` |
| pip | 21+ | `pip --version` |
| Node.js | 18 | `node --version` |
| npm | 9+ | `npm --version` |

> **macOS:** install Python via [python.org](https://www.python.org/downloads/) or `brew install python`. Install Node via [nodejs.org](https://nodejs.org/) or `brew install node`.  
> **Windows:** install Python from [python.org](https://www.python.org/downloads/) (tick "Add to PATH") and Node from [nodejs.org](https://nodejs.org/).

---

### Step 1 — Start the API backend

Open a terminal and run:

```bash
# 1. Go into the backend folder
cd "Project2026 copy"

# 2. Install Python dependencies (only needed once)
pip install -r requirements.txt

# 3. Start the API server
uvicorn api:app --host 0.0.0.0 --port 8000
```

Wait until you see a line like this (takes ~5 seconds while the ML model trains):

```
[STARTUP] Ready — model trained in 4.2s | threshold=0.152 | AUC=0.739 | Recall=0.810
```

The API is now running at **http://localhost:8000**.  
You can explore the interactive API docs at **http://localhost:8000/docs**.

---

### Step 2 — Start the Next.js frontend

Open a **second** terminal (keep the first one running) and run:

```bash
# 1. Go into the frontend folder
cd frontend

# 2. Install Node dependencies (only needed once)
npm install

# 3. Copy the environment config (only needed once)
cp .env.example .env.local

# 4. Start the dev server
npm run dev
```

Once you see `✓ Ready - started server on 0.0.0.0:3000`, open your browser and go to:

> **http://localhost:3000**

---

### What you'll see

| Page | URL | Description |
|------|-----|-------------|
| Dashboard | http://localhost:3000 | Live model stats, pipeline diagram, system status |
| Analysis | http://localhost:3000/analysis | Configure a payment → run Score → CVA Pricing → Bridge Loan cascade |
| Portfolio | http://localhost:3000/portfolio | Session charts and loan results table |
| Audit Trail | http://localhost:3000/audit | Claim 5(x) records with JSON/CSV export |

---

### Stopping the servers

Press **Ctrl + C** in each terminal to stop the API and the frontend dev server.

---

## Repository layout

```
PRKT2026/
├── Project2026 copy/       ← Python FastAPI backend + ML engines
│   ├── api.py              ← FastAPI app (start with uvicorn)
│   ├── failure_prediction_engine.py
│   ├── cva_pricing_engine.py
│   ├── bridge_loan_execution.py
│   ├── dashboard.py        ← Optional Streamlit dashboard (port 8501)
│   └── requirements.txt
└── frontend/               ← Next.js 14 App Router dashboard
    ├── app/                ← Pages (dashboard, analysis, portfolio, audit)
    ├── components/         ← UI components
    └── lib/                ← API client, Zustand store, utilities
```

## Architecture

| Component | File | Patent Claims |
|-----------|------|---------------|
| 1 — Failure Prediction | `failure_prediction_engine.py` | 1(a–d), D1, D3, D9 |
| 2 — CVA Pricing | `cva_pricing_engine.py` | 1(e), D4, D5, D6, D7 |
| 3 — Bridge Execution | `bridge_loan_execution.py` | 1(f–h), 3(m), 5(t–x), D11 |
| 4 — API | `api.py` | D9 (latency enforcement) |

## Environment variables

The frontend reads one variable from `frontend/.env.local`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | URL of the FastAPI backend |

To point the frontend at a different backend host, edit `frontend/.env.local` before running `npm run dev`.

The backend reads one optional variable:

| Variable | Default | Purpose |
|----------|---------|---------|
| `ALBS_CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated list of allowed browser origins |

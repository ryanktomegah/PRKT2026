# ALBS Frontend

**Automated Liquidity Bridging System** — Next.js 14 dashboard for Patent Spec v4.0.

## Prerequisites

- Node.js 18+
- The FastAPI backend running on `http://localhost:8000`

## Setup

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | FastAPI backend URL |

## Backend CORS

The FastAPI backend (`Project2026 copy/api.py`) needs CORS middleware to accept browser requests. Add the following to `api.py` after the app is created:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard — system status, pipeline overview, session metrics |
| `/analysis` | Main analysis page — configure a payment and run Score → Price → Execute cascade |
| `/portfolio` | Portfolio analytics — charts and table accumulated across the session |
| `/audit` | Audit trail — expandable JSON records, export as JSON/CSV |

## Tech Stack

- **Next.js 14** (App Router)
- **Tailwind CSS** — dark theme with slate/navy palette
- **Framer Motion** — cascade animations, gauge, bar transitions
- **Recharts** — probability histogram, APR bars, offer status donut
- **Zustand** — session-level portfolio accumulation
- **TanStack Query** — API fetching, health polling

## Building for Production

```bash
npm run build
npm start
```

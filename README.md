
# Auto Buyer Demo (Ingest → Normalize → Score → Review → Notify)

This is a minimal demo showing an end-to-end buyer workflow:

- Backend (FastAPI): ingest, list, score, and notify endpoints. Optional Postgres persistence.
- DB: starter Postgres schema for listings, vehicles, and scores keyed by VIN.
- Frontend (Next.js + Tailwind): Buyer Review UI with load/seed actions, sortable table, and scoring.


## Quickstart (Local, no DB required)

1) Backend (FastAPI)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload --port 8001
```

2) Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:3000

Frontend controls:
- Load from Backend: GET /listings
- Seed Backend: POST /ingest with 3 demo listings
- Re-score Visible: POST /score (persists to backend in-memory or DB)
- Notify: POST /notify for a specific VIN


## Optional: Postgres persistence

Set `DATABASE_URL` and the backend will store `vehicles`, `listings`, and `scores` in Postgres. The schema is auto-applied from `db/schema.sql` at startup.

Example connection string:
```
postgresql://USER:PASSWORD@localhost:5432/auto_buyer
```

Steps:
```bash
createdb auto_buyer                     

cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8001
```

Endpoints (when DB is enabled, writes go to Postgres; otherwise use in-memory storage):
- GET `/healthz`
- POST `/ingest`: normalize + store listings
- GET `/listings`: list stored listings joined with latest score
- POST `/score`: compute and persist scores
- POST `/notify`: demo notify recorder


## Architecture Diagram
![Auto Buyer Architecture](assets/auto_pipeline_diagram.png)

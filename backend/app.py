
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    import psycopg
    _psycopg_available = True
except Exception:
    psycopg = None  # type: ignore
    _psycopg_available = False

app = FastAPI(title="Auto Buyer Demo – Scoring Stub")

# CORS for local Next.js dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Listing(BaseModel):
    vin: str
    price: float
    miles: int
    dom: int  # days on market
    source: Optional[str] = None

class ScoreResponse(BaseModel):
    vin: str
    score: int = Field(..., ge=0, le=100)
    buyMax: float
    reasonCodes: List[str]


class StoredListing(BaseModel):
    id: str
    vin: str
    year: int
    make: str
    model: str
    trim: Optional[str] = None
    miles: int
    price: float
    score: Optional[int] = None
    dom: int
    source: Optional[str] = None
    radius: Optional[int] = 25
    reasonCodes: List[str] = []
    buyMax: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# In-memory stores for demo
_by_id: Dict[str, StoredListing] = {}
_ids_by_vin: Dict[str, List[str]] = {}
_notifications: List[Dict[str, str]] = []


# Optional Postgres integration (enabled when DATABASE_URL is set and psycopg is available)
DATABASE_URL = os.getenv("DATABASE_URL")
_db_enabled: bool = bool(DATABASE_URL and _psycopg_available)


def _get_db_connection() -> Optional["psycopg.Connection"]:
    if not _db_enabled:
        return None
    assert psycopg is not None
    return psycopg.connect(DATABASE_URL, autocommit=True)  # type: ignore


def _apply_schema_if_needed() -> None:
    conn = _get_db_connection()
    if not conn:
        return
    try:
        with conn, conn.cursor() as cur:
            # Attempt to create tables by executing bundled schema
            schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "schema.sql")
            try:
                with open(schema_path, "r", encoding="utf-8") as f:
                    sql = f.read()
                cur.execute(sql)
            except FileNotFoundError:
                # Fallback: minimal DDL inline
                cur.execute(
                    """
                    create table if not exists vehicles (
                      vin text primary key,
                      year int,
                      make text,
                      model text,
                      trim text
                    );
                    create table if not exists listings (
                      id serial primary key,
                      vin text references vehicles(vin),
                      source text,
                      price numeric,
                      miles int,
                      dom int,
                      payload jsonb,
                      created_at timestamptz default now()
                    );
                    create table if not exists scores (
                      id serial primary key,
                      vin text references vehicles(vin),
                      score int check (score between 0 and 100),
                      buy_max numeric,
                      reason_codes text[],
                      created_at timestamptz default now()
                    );
                    create or replace view v_latest_scores as
                    select distinct on (vin) vin, score, buy_max, reason_codes, created_at
                    from scores
                    order by vin, created_at desc;
                    """
                )
    finally:
        conn.close()


if _db_enabled:
    _apply_schema_if_needed()

@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/ingest", response_model=List[StoredListing])
def ingest(listings: List[StoredListing]):
    """
    Ingest listings into the demo store (acts as Normalize+Store steps).
    Normalization applied:
    - VIN uppercased and stripped
    - Default radius to 25 if missing
    - Trim text fields strip
    """
    out: List[StoredListing] = []
    if _db_enabled:
        conn = _get_db_connection()
        assert conn is not None
        try:
            with conn, conn.cursor() as cur:
                for item in listings:
                    norm = item.copy(deep=True)
                    norm.vin = (norm.vin or "").strip().upper()
                    norm.make = (norm.make or "").strip()
                    norm.model = (norm.model or "").strip()
                    if norm.trim is not None:
                        norm.trim = norm.trim.strip()
                    if not norm.radius:
                        norm.radius = 25
                    # vehicles upsert
                    cur.execute(
                        """
                        insert into vehicles (vin, year, make, model, trim)
                        values (%s, %s, %s, %s, %s)
                        on conflict (vin) do update set year = excluded.year, make = excluded.make, model = excluded.model, trim = excluded.trim
                        """,
                        (norm.vin, norm.year, norm.make, norm.model, norm.trim),
                    )
                    # listings insert
                    cur.execute(
                        """
                        insert into listings (vin, source, price, miles, dom, payload)
                        values (%s, %s, %s, %s, %s, %s)
                        returning id
                        """,
                        (norm.vin, norm.source, norm.price, norm.miles, norm.dom, json.dumps(norm.model_dump())),
                    )
                    new_id = cur.fetchone()[0]
                    norm.id = str(new_id)
                    out.append(norm)
        finally:
            conn.close()
        return out
    # In-memory fallback
    for item in listings:
        norm = item.copy(deep=True)
        norm.vin = (norm.vin or "").strip().upper()
        norm.make = (norm.make or "").strip()
        norm.model = (norm.model or "").strip()
        if norm.trim is not None:
            norm.trim = norm.trim.strip()
        if not norm.radius:
            norm.radius = 25
        _by_id[norm.id] = norm
        _ids_by_vin.setdefault(norm.vin, [])
        if norm.id not in _ids_by_vin[norm.vin]:
            _ids_by_vin[norm.vin].append(norm.id)
        out.append(norm)
    return out


@app.get("/listings", response_model=List[StoredListing])
def list_listings():
    """Return all listings currently stored with latest score fields."""
    if _db_enabled:
        conn = _get_db_connection()
        assert conn is not None
        try:
            with conn, conn.cursor() as cur:
                cur.execute(
                    """
                    select l.id, l.vin, coalesce(v.year, 0) as year, coalesce(v.make,''), coalesce(v.model,''), v.trim,
                           l.miles, l.price, l.dom, l.source,
                           s.score, s.buy_max, s.reason_codes
                    from listings l
                    left join vehicles v on v.vin = l.vin
                    left join v_latest_scores s on s.vin = l.vin
                    order by l.created_at desc
                    limit 500
                    """
                )
                rows = cur.fetchall()
                out: List[StoredListing] = []
                for rid, vin, year, make, model, trim, miles, price, dom, source, score, buy_max, reason_codes in rows:
                    out.append(
                        StoredListing(
                            id=str(rid),
                            vin=vin,
                            year=int(year),
                            make=make,
                            model=model,
                            trim=trim,
                            miles=int(miles),
                            price=float(price),
                            score=int(score) if score is not None else None,
                            dom=int(dom),
                            source=source,
                            radius=25,
                            reasonCodes=reason_codes or [],
                            buyMax=float(buy_max) if buy_max is not None else None,
                        )
                    )
                return out
        finally:
            conn.close()
    return list(_by_id.values())


class NotifyItem(BaseModel):
    vin: str
    channel: Optional[str] = "email"
    message: Optional[str] = None


class NotifyResponse(BaseModel):
    vin: str
    notified: bool
    channel: str


@app.post("/notify", response_model=List[NotifyResponse])
def notify(items: List[NotifyItem]):
    """Demo notify endpoint that records notifications in memory and returns status."""
    results: List[NotifyResponse] = []
    for it in items:
        vin_key = (it.vin or "").strip().upper()
        msg = it.message or f"Notify for VIN {vin_key}"
        _notifications.append({"vin": vin_key, "channel": it.channel or "email", "message": msg})
        results.append(NotifyResponse(vin=vin_key, notified=True, channel=(it.channel or "email")))
    return results

@app.post("/score", response_model=List[ScoreResponse])
def score(listings: List[Listing]):
    r"""
    Tiny heuristic demo:
    - Base score from inverse DOM and miles
    - Price delta heuristic (lower price vs. naive baseline = higher score)
    - Reason codes emitted based on thresholds
    """
    out: List[ScoreResponse] = []
    for item in listings:
        reasons = []
        # naive baselines
        dom_penalty = max(0, 30 - item.dom) / 30  # 0..1
        miles_penalty = max(0, 100_000 - item.miles) / 100_000  # 0..1
        base = 40 * dom_penalty + 40 * miles_penalty

        # price heuristic: cheaper than $25k gets boost (purely for demo)
        price_boost = 0
        if item.price < 25000:
            price_boost = min(20, (25000 - item.price) / 1000)
            reasons.append("PriceVsBaseline")
        if item.dom < 20:
            reasons.append("LowDOM")
        if item.miles < 50000:
            reasons.append("LowMiles")

        score_val = int(max(0, min(100, base + price_boost)))
        buy_max = max(0.0, item.price * 1.03)  # naive +3% wiggle room

        # tighten buy max if DOM is high
        if item.dom > 45:
            buy_max = item.price * 0.98
            reasons.append("AgedInventory")

        # persist onto any stored listing(s) that match this VIN
        vin_key = (item.vin or "").strip().upper()
        if _db_enabled:
            conn = _get_db_connection()
            assert conn is not None
            try:
                with conn, conn.cursor() as cur:
                    cur.execute(
                        """
                        insert into scores (vin, score, buy_max, reason_codes)
                        values (%s, %s, %s, %s)
                        """,
                        (vin_key, score_val, round(buy_max, 2), reasons or ["Heuristic"]),
                    )
            finally:
                conn.close()
        for lid in _ids_by_vin.get(vin_key, []):
            stored = _by_id.get(lid)
            if stored:
                stored.score = score_val
                stored.buyMax = round(buy_max, 2)
                stored.reasonCodes = reasons or ["Heuristic"]
                _by_id[lid] = stored

        out.append(ScoreResponse(vin=item.vin, score=score_val, buyMax=round(buy_max, 2), reasonCodes=reasons or ["Heuristic"]))

    return out

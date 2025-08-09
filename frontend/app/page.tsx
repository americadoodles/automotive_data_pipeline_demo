
'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowUpDown, Car, Gauge, DollarSign, Clock, Tag } from 'lucide-react';

type Listing = {
  id: string;
  vin: string;
  year: number;
  make: string;
  model: string;
  trim?: string;
  miles: number;
  price: number;
  score: number;
  dom: number;
  source: string;
  radius: number;
  reasonCodes: string[];
  buyMax: number;
};

const MOCK: Listing[] = [
  { id:'1', vin:'1HGCM82633A004352', year:2019, make:'Toyota', model:'Camry', trim:'SE', miles:41000, price:18950, score:88, dom:27, source:'AutoTrader', radius:52, reasonCodes:['PriceVsBaseline','LowDOM'], buyMax:19600 },
  { id:'2', vin:'1C4RJEBG3MC123456', year:2021, make:'Jeep', model:'Grand Cherokee', trim:'Limited', miles:36000, price:27990, score:73, dom:44, source:'Facebook Marketplace', radius:18, reasonCodes:['LowMiles'], buyMax:28600 },
  { id:'3', vin:'5YJ3E1EA7KF317000', year:2019, make:'Tesla', model:'Model 3', trim:'Long Range', miles:58000, price:21900, score:92, dom:12, source:'Bring a Trailer', radius:420, reasonCodes:['PriceVsBaseline','LowDOM'], buyMax:23000 },
];

const currency = (n:number) => n.toLocaleString('en-US', { style:'currency', currency:'USD', maximumFractionDigits:0 });

export default function Page() {
  const [data, setData] = useState<Listing[]>(MOCK);
  const [sort, setSort] = useState<{key: keyof Listing; dir:'asc'|'desc'}>({ key:'score', dir:'desc' });
  const [loading, setLoading] = useState<boolean>(false);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8001';

  const rows = useMemo(() => {
    const dir = sort.dir === 'asc' ? 1 : -1;
    return [...data].sort((a,b) => {
      const av = a[sort.key] as any;
      const bv = b[sort.key] as any;
      if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir;
      return String(av).localeCompare(String(bv)) * dir;
    });
  }, [data, sort]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const hz = await fetch(`${BACKEND}/healthz`);
        if (!hz.ok) throw new Error('backend not ready');
        if (!mounted) return;
        setBackendOk(true);
        const resp = await fetch(`${BACKEND}/listings`);
        if (resp.ok) {
          const list = await resp.json();
          if (mounted && Array.isArray(list) && list.length > 0) {
            setData(list);
          }
        }
      } catch {
        if (!mounted) return;
        setBackendOk(false);
      }
    })();
    return () => { mounted = false; };
  }, [BACKEND]);

  async function rescoreVisible() {
    try {
      const payload = rows.map(r => ({ vin: r.vin, price: r.price, miles: r.miles, dom: r.dom, source: r.source }));
      const resp = await fetch(`${BACKEND}/score`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
      if (!resp.ok) throw new Error('Bad response');
      const scores = await resp.json();
      const byVin: Record<string, {score:number; buyMax:number; reasonCodes:string[]}> = {};
      for (const s of scores) byVin[s.vin] = { score: s.score, buyMax: s.buyMax, reasonCodes: s.reasonCodes };
      setData(d => d.map(x => byVin[x.vin] ? { ...x, ...byVin[x.vin] } : x));
      alert(`Re-scored ${scores.length} listings.`);
    } catch (e:any) {
      alert('Failed to score: ' + e.message);
    }
  }

  async function seedBackend() {
    try {
      setLoading(true);
      const resp = await fetch(`${BACKEND}/ingest`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(MOCK) });
      if (!resp.ok) throw new Error('Failed to ingest');
      const seeded = await resp.json();
      setData(seeded);
      setBackendOk(true);
      alert(`Seeded ${seeded.length} listings to backend.`);
    } catch (e:any) {
      alert('Failed to seed backend: ' + e.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadFromBackend() {
    try {
      setLoading(true);
      const resp = await fetch(`${BACKEND}/listings`);
      if (!resp.ok) throw new Error('Failed to load listings');
      const list = await resp.json();
      setData(Array.isArray(list) && list.length ? list : data);
      setBackendOk(true);
    } catch (e:any) {
      alert('Failed to load from backend: ' + e.message);
    } finally {
      setLoading(false);
    }
  }

  async function notify(vin: string) {
    try {
      setLoading(true);
      const resp = await fetch(`${BACKEND}/notify`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify([{ vin }]) });
      if (!resp.ok) throw new Error('Failed to notify');
      const res = await resp.json();
      alert(`Notified for VIN ${vin}: ${res?.[0]?.channel ?? 'ok'}`);
    } catch (e:any) {
      alert('Failed to notify: ' + e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="mx-auto max-w-6xl space-y-4">
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-slate-900 p-2 text-white shadow"><Car className="h-6 w-6" /></div>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">Buyer Review Queue</h1>
              <p className="text-sm text-slate-600">Ingest → Normalize → Score → Review → Notify</p>
            </div>
          </div>
          <div className="flex gap-2">
            <button className="rounded-xl bg-slate-100 px-3 py-2 text-sm hover:bg-slate-200" onClick={loadFromBackend} disabled={loading}>Load from Backend</button>
            <button className="rounded-xl bg-slate-100 px-3 py-2 text-sm hover:bg-slate-200" onClick={seedBackend} disabled={loading}>Seed Backend</button>
            <button className="rounded-xl bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-800" onClick={rescoreVisible} disabled={loading}>Re-score Visible</button>
          </div>
        </header>

        {backendOk === false && (
          <div className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-amber-900">Backend not reachable at {BACKEND}. Using in-memory demo data.</div>
        )}

        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="grid grid-cols-12 bg-slate-50 px-4 py-2 text-xs font-medium uppercase tracking-wide text-slate-600">
            {[
              { key: 'score', label: 'Score' },
              { key: 'vin', label: 'VIN' },
              { key: 'year', label: 'Year' },
              { key: 'make', label: 'Make' },
              { key: 'model', label: 'Model' },
              { key: 'miles', label: 'Miles' },
              { key: 'price', label: 'Price' },
              { key: 'dom', label: 'DOM' },
              { key: 'source', label: 'Source' },
              { key: 'radius', label: 'Radius' },
              { key: 'buyMax', label: 'Buy-Max' },
              { key: 'actions', label: '' },
            ].map(col => (
              <button key={col.key} className="col-span-1 flex items-center gap-1" onClick={() => setSort(s => ({ key: (col.key as keyof Listing) ?? s.key, dir: s.dir === 'asc' ? 'desc' : 'asc' }))}>
                <span>{col.label}</span>
                {col.key !== 'actions' && <ArrowUpDown className="h-3 w-3" />}
              </button>
            ))}
          </div>

          {rows.map(r => (
            <div key={r.id} className="grid grid-cols-12 items-center border-t px-4 py-3 text-sm hover:bg-slate-50">
              <div className="col-span-1 font-semibold"><span className="rounded-full bg-slate-100 px-2 py-1">{r.score}</span></div>
              <div className="col-span-1 truncate text-xs text-slate-600">{r.vin}</div>
              <div className="col-span-1">{r.year}</div>
              <div className="col-span-1">{r.make}</div>
              <div className="col-span-1">{r.model}</div>
              <div className="col-span-1 flex items-center gap-1"><Gauge className="h-3 w-3" /> {r.miles.toLocaleString('en-US')}</div>
              <div className="col-span-1 flex items-center gap-1"><DollarSign className="h-3 w-3" /> {currency(r.price)}</div>
              <div className="col-span-1 flex items-center gap-1"><Clock className="h-3 w-3" /> {r.dom}d</div>
              <div className="col-span-1">{r.source}</div>
              <div className="col-span-1">{r.radius} mi</div>
              <div className="col-span-1 font-medium">{r.buyMax != null ? currency(r.buyMax) : '—'}</div>
              <div className="col-span-1 flex gap-2">
                <button className="text-blue-600 hover:underline" onClick={() => notify(r.vin)}>Notify</button>
              </div>
            </div>
          ))}
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <Kpi label="Avg Profit / Unit" value="$2,140" />
          <Kpi label="Lead → Purchase" value="3.2 days" />
          <Kpi label="Aged Inventory" value="4 units" />
        </div>
      </motion.div>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}

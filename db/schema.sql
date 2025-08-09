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

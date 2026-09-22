-- SafeWatch Supabase schema
-- Run this file once in Supabase SQL Editor before using STORAGE_BACKEND=postgres.

create table if not exists facilities (
  id text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);

create table if not exists rooms (
  id text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);

create table if not exists staff (
  id text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);

create table if not exists residents (
  id text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);

create table if not exists devices (
  id text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);

create table if not exists assignments (
  id text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);

create table if not exists alerts (
  id text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);

create table if not exists telemetry_records (
  id bigint generated always as identity primary key,
  event_at timestamptz not null,
  data jsonb not null
);

create index if not exists telemetry_records_event_at_idx on telemetry_records (event_at);

-- The FastAPI server uses the database connection string directly.
-- Keep these tables private; do not enable public anonymous access for them.
revoke all on all tables in schema public from anon, authenticated;
grant all on all tables in schema public to postgres, service_role;

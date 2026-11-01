-- Tables used by the cinema-push Edge Function, in the shared Supabase project "family-apps"
-- (emgtyfksnofzzlutngbf). Only cinema_* tables belong to this app; never touch the others.
-- Documented from the live database on 2026-11-01. RLS is ON for all of them with no policies,
-- so only the Edge Function (service role) can read or write.

create table if not exists public.cinema_prefs (          -- family users' marks: one row per user (oren, lior, evyatar)
  id         text primary key default 'default',
  fav        jsonb not null default '[]'::jsonb,           -- ★ favorites (movie titles)
  seen       jsonb not null default '[]'::jsonb,           -- ✓ watched (movie titles), kept forever
  updated_at timestamptz not null default now()
);

create table if not exists public.cinema_push (           -- family devices subscribed to Web Push
  endpoint   text primary key,
  p256dh     text not null,
  auth       text not null,
  user_id    text not null default 'guest',              -- oren | lior | evyatar | guest
  created_at timestamptz not null default now()
);

create table if not exists public.cinema_public_prefs (   -- public app (docs/app/): anonymous visitor marks
  id         uuid primary key,                             -- random id per browser (localStorage cc-pid)
  fav        text[] not null default '{}',
  seen       text[] not null default '{}',
  updated_at timestamptz not null default now()
);

create table if not exists public.cinema_public_push (    -- public app devices
  endpoint   text primary key,
  p256dh     text not null,
  auth       text not null,
  pid        uuid,
  created_at timestamptz not null default now()
);

create table if not exists public.cinema_push_log (       -- one row per scan, so a scan is pushed only once
  generated_at text primary key,
  sent         integer,
  sent_at      timestamptz not null default now()
);

create table if not exists public.cinema_secrets (        -- key/value, server-only. Names (values are NOT in git):
  name  text primary key,                                  --   vapid_public, vapid_private (generated on first use),
  value text not null                                      --   user_password (family login), upcoming_known,
);                                                         --   released_last (state for de-duplication)

alter table public.cinema_prefs        enable row level security;
alter table public.cinema_push         enable row level security;
alter table public.cinema_public_prefs enable row level security;
alter table public.cinema_public_push  enable row level security;
alter table public.cinema_push_log     enable row level security;
alter table public.cinema_secrets      enable row level security;

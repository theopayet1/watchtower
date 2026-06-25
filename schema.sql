-- Watch memory schema (paste into the Supabase SQL editor).
-- Creates the 3 tables that state.py reads/writes in Supabase mode.

-- 1) seen_items : deduplication memory + later lookup.
--    Stores enough to FIND an item again (title/url/source) and a free "note"
--    column for your own comments/tags.
create table if not exists seen_items (
    id        text primary key,        -- unique item id, e.g. "rss:https://..."
    seen_at   timestamptz not null default now(),
    title     text,
    url       text,
    source    text,
    published text,
    note      text                     -- free text: your comments / tags (search this later)
);

-- Migration for an EXISTING seen_items table (safe to re-run; no-op if already there):
alter table seen_items add column if not exists title     text;
alter table seen_items add column if not exists url       text;
alter table seen_items add column if not exists source    text;
alter table seen_items add column if not exists published text;
alter table seen_items add column if not exists note      text;

-- 2) digests : history of every digest sent.
create table if not exists digests (
    id         bigint generated always as identity primary key,
    created_at timestamptz not null default now(),
    content    text not null
);

-- 3) feedback : your notes to steer the next summary.
create table if not exists feedback (
    id         bigint generated always as identity primary key,
    created_at timestamptz not null default now(),
    note       text not null,           -- e.g. "focus more on open-source model releases"
    applied    boolean not null default false,
    applied_at timestamptz
);

-- Index to quickly find feedback not yet applied.
create index if not exists feedback_not_applied_idx on feedback (applied) where applied = false;

-- Schéma de la mémoire de la veille (à coller dans l'éditeur SQL de Supabase).
-- Crée les 3 tables que state.py lit/écrit en mode Supabase.

-- 1) seen_items : mémoire du dédoublonnage (les articles déjà traités)
create table if not exists seen_items (
    id      text primary key,                         -- id unique de l'item, ex. "rss:https://..."
    seen_at timestamptz not null default now()
);

-- 2) digests : historique des synthèses envoyées
create table if not exists digests (
    id         bigint generated always as identity primary key,
    created_at timestamptz not null default now(),
    content    text not null
);

-- 3) feedback : tes retours pour ajuster la synthèse du run suivant
create table if not exists feedback (
    id         bigint generated always as identity primary key,
    created_at timestamptz not null default now(),
    note       text not null,                          -- ex. "développe plus l'IA"
    applied    boolean not null default false,         -- passe à true une fois pris en compte
    applied_at timestamptz
);

-- Index pour retrouver vite les feedbacks non encore appliqués
create index if not exists feedback_not_applied_idx on feedback (applied) where applied = false;

# Architecture

## Pipeline data flow

The pipeline knows nothing about the details of each source. It calls each
collector, gets back items in the **same shape**, then chains dedup → summarize →
deliver. Adding a source later = one new `collect/xxx.py` returning that shape.

```
sources.yaml ──► config.py
                    │
                    ▼
            ┌──────────────────┐   for each category
            │   pipeline.py    │◄──────────────────────────┐
            │ (the conductor)  │                            │
            └────────┬─────────┘                            │
                     ▼                                      │
   collect/  ┌──── rss ──── hackernews ────┐  ───────►  raw items
                     ▼
            state.filter_new()      ── drop anything already seen
                     ▼
            synthesize.synthesize() ── Claude summarizes (or raw list if no key)
                     ▼
            deliver_email.send()    ── email via HTTP API (or file fallback)
                     ▼
            state.mark_seen()       ── mark as seen, AFTER successful delivery
```

---

## Production architecture (cloud, laptop-off)

The code lives on GitHub (no secrets). A Claude Code **cloud routine** clones it on
a schedule, injects the secrets as environment variables, and runs `pipeline.py`.
State lives in Supabase so it survives between runs — the cloud environment is
destroyed after each run.

```
        ┌────────────────────────────────────────────────────────────┐
        │  GitHub  ·  theopayet1/watchtower   (code only — NO secrets) │
        └───────────────────────────┬────────────────────────────────┘
                                     │  fresh clone every run
                 daily schedule      ▼
        ┌────────────────────────────────────────────────────────────┐
        │           CLAUDE CODE CLOUD ROUTINE                          │
        │           (Anthropic infra — runs with laptop off)           │
        │                                                              │
        │   environment variables (secrets, set in the UI):            │
        │     VEILLE_ANTHROPIC_API_KEY · BREVO_API_KEY                 │
        │     SUPABASE_URL · SUPABASE_KEY · APP_ENV=prod               │
        │   setup script :  pip install -r requirements.txt            │
        │   command      :  python pipeline.py                         │
        └───────┬───────────────────┬───────────────────┬─────────────┘
                │ collect           │ state             │ summarize + deliver
       (HTTPS)  ▼                   ▼                   ▼
     ┌────────────────┐   ┌──────────────────┐   ┌──────────────────┐
     │  RSS feeds  +  │   │  Supabase        │   │  Claude API      │
     │  Hacker News   │   │  (PostgreSQL)    │   │  (api.anthropic) │
     │  (public)      │   │  seen / digests  │   └──────────────────┘
     └────────────────┘   │  / feedback      │   ┌──────────────────┐
                          └──────────────────┘   │  Brevo API       │
                                                  │  (HTTPS 443)     │
                                                  └────────┬─────────┘
                                                           ▼
                                                     📧  your inbox
```

### Why each external piece exists

| Piece | Role | Why it must be external |
|-------|------|-------------------------|
| **GitHub** | Holds the code | The routine clones it each run. `.env` is gitignored — secrets never go here. |
| **Supabase** | State (dedup, history, feedback) | The cloud env is wiped after each run; a local `seen.json` wouldn't survive. |
| **Claude API** | Summarization | Billed separately from the Claude subscription (prepaid credits). |
| **Brevo** | Email delivery over HTTPS | SMTP egress (25/587) is often blocked in cloud sandboxes; an HTTP API on 443 is reliable. |

See [deployment.md](deployment.md) for the network-allowlist and reserved-env-var
gotchas these introduce.

---

## The common "item" format (the glue)

Every collector returns a list of identical dictionaries:

```python
{
    "id":        "rss:https://…",     # UNIQUE id → deduplication key
    "source":    "TechCrunch",        # shown in the digest
    "title":     "...",
    "url":       "https://...",
    "score":     128,                 # points/upvotes (None if not applicable)
    "published": "2026-06-23T...",    # ISO date or epoch
    "summary":   "..."                # optional excerpt
}
```

This contract lets `state.py`, `synthesize.py`, and `deliver_email.py` process any
source without knowing where it came from. The `id` prefix (`rss:`, `hn:`) prevents
collisions between sources.

---

## State backends & data model

`state.py` exposes one interface — `filter_new`, `mark_seen`, `save_digest`,
`pending_feedback`, `mark_feedback_applied` — with two implementations, selected
automatically:

```
SUPABASE_URL and SUPABASE_KEY set?
        ├── yes → Supabase (PostgreSQL)   ← required in the cloud
        └── no  → local files in state/   ← fine for dev
```

The pipeline prints which backend is active at startup
(`État : Supabase` / `local JSON`).

### Supabase tables (`schema.sql`)

```
┌─ seen_items ──────────────┐   deduplication memory
│  id        text  (PK)     │   one row per article ever processed
│  seen_at   timestamptz    │
└───────────────────────────┘

┌─ digests ─────────────────┐   history
│  id         bigint (PK)   │   every digest that was sent, archived
│  created_at timestamptz   │
│  content    text          │
└───────────────────────────┘

┌─ feedback ────────────────┐   steering
│  id         bigint (PK)   │   insert a note → applied to the next summary,
│  created_at timestamptz   │   then marked applied (applied once)
│  note       text          │
│  applied    boolean       │
│  applied_at timestamptz   │
└───────────────────────────┘
```

Create them once: open the Supabase SQL editor, paste `schema.sql`, run.

---

## Two mechanisms worth understanding

- **Deduplication.** `filter_new()` drops what's already stored *and* what's
  duplicated inside the current batch (same article via two sources). Run the
  pipeline twice in a row → the second run reports "nothing new".
- **Mark-seen ordering.** `mark_seen()` runs **only after** `deliver_email.send()`
  succeeds. A crash mid-run leaves items unmarked, so the next run re-collects them
  — you never silently lose news.

# 🗞️ Watchtower — Automated News Watch

A small, dependency-light pipeline that **collects news by category (RSS + Hacker
News), removes what you've already seen, has Claude summarize it, and emails you a
daily digest**.

It runs locally for development and, in production, as a **scheduled Claude Code
cloud routine** — on Anthropic's infrastructure, on a daily schedule, **even when
your laptop is closed**.

> The digest content is written in **French** (the prompt enforces it, and the
> default sources are French). This documentation is in English.

---

## 1. Pipeline data flow

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

The pipeline knows nothing about the details of each source. It calls each
collector, gets back items in the **same shape**, then chains dedup → summarize →
deliver. Adding a source later = one new `collect/xxx.py` returning that shape.

---

## 2. Production architecture (cloud, laptop-off)

The whole point: the code lives on GitHub (no secrets), and a Claude Code **cloud
routine** clones it on a schedule, injects the secrets as environment variables,
and runs `pipeline.py`. State lives in Supabase so it survives between runs (the
cloud environment is destroyed after each run).

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

**Why each external piece exists**

| Piece | Role | Why it must be external |
|-------|------|-------------------------|
| **GitHub** | Holds the code | The routine clones it each run. `.env` is gitignored — secrets never go here. |
| **Supabase** | State (dedup, history, feedback) | The cloud env is wiped after each run; a local `seen.json` wouldn't survive. |
| **Claude API** | Summarization | Billed separately from the Claude subscription (prepaid credits). |
| **Brevo** | Email delivery over HTTPS | SMTP egress (25/587) is often blocked in cloud sandboxes; an HTTP API on 443 is reliable. |

> ⚠️ **Cloud network allowlist.** The routine's environment blocks non-allowlisted
> domains (`403 host_not_allowed`). Add `api.anthropic.com`, `api.brevo.com`, and
> your Supabase host to the environment's **Allowed domains** (or use **Full**
> network access), or the calls will fail.

> ⚠️ **Reserved env var name.** On Claude Code cloud, `ANTHROPIC_API_KEY` is
> reserved by the platform and is **not** passed to your script. Set the key as
> **`VEILLE_ANTHROPIC_API_KEY`** instead — `config.py` reads that first and falls
> back to `ANTHROPIC_API_KEY` for local dev.

---

## 3. The common "item" format (the glue)

Every collector returns a list of identical dictionaries:

```python
{
    "id":        "rss:https://…",     # UNIQUE id → deduplication key
    "source":    "ActuIA",            # shown in the digest
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

## 4. Project layout

```
watchtower/
├── pipeline.py          ← entry point — this is what runs (locally and in the routine)
├── config.py            ← loads .env + sources.yaml; single source of keys & app mode
├── sources.yaml         ← YOUR editable config: categories, feeds, keywords
├── state.py             ← persistence: dedup + history + feedback (local OR Supabase)
├── synthesize.py        ← builds the prompt + calls Claude (fallback: raw list)
├── deliver_email.py     ← email via Resend/Brevo/SMTP, with a file fallback
├── preview.py           ← read-only preview of what the collectors return
├── schema.sql           ← the 3 Supabase tables (paste into the SQL editor)
├── requirements.txt
├── .env.example         ← template for secrets (copy to .env locally)
├── .gitignore           ← excludes .env, .venv, state/, digests/, …
├── collect/             ← one module per source
│   ├── __init__.py
│   ├── rss.py           ← any RSS/Atom feed (no key)
│   └── hackernews.py    ← Hacker News via the Algolia API (no key)
├── state/               ← generated locally (dev backend only)
│   ├── seen.json        ← local dedup memory
│   └── feedback.md      ← drop a line here to steer the next summary (local mode)
├── digests/             ← generated locally: one .md per run (dev backend only)
└── last_digest.md       ← generated: email fallback output when no backend is set
```

### File responsibilities

| File | Role |
|------|------|
| `config.py` | Loads `.env` + `sources.yaml`. Exposes keys, `APP_ENV`/`IS_PROD`. Paths resolved relative to the file, so it works regardless of the working directory (cloud-safe). |
| `sources.yaml` | Your editable config: categories, RSS feeds, HN keywords. **The only file you touch day to day.** |
| `collect/rss.py` | `feedparser` reads any feed; filters by date with `calendar.timegm` (UTC-correct) and decodes HTML entities. |
| `collect/hackernews.py` | HN Algolia API, filters by freshness server-side. No key. |
| `state.py` | Memory between runs. Same interface, two backends (local JSON / Supabase). |
| `synthesize.py` | Builds the prompt, calls Claude. Falls back to a markdown list if no key (dev only). |
| `deliver_email.py` | Picks an email backend and sends. Falls back to `last_digest.md` (dev only). |
| `pipeline.py` | The orchestrator + the `preflight()` check. |
| `preview.py` | Read-only: prints collected items without touching state. Great for testing a new feed. |

---

## 5. State backends & data model

`state.py` exposes one interface — `filter_new`, `mark_seen`, `save_digest`,
`pending_feedback`, `mark_feedback_applied` — with two implementations, selected
automatically:

```
SUPABASE_URL and SUPABASE_KEY set?
        ├── yes → Supabase (PostgreSQL)   ← required in the cloud
        └── no  → local files in state/   ← fine for dev
```

The pipeline prints which one is active at startup (`État : Supabase` / `local JSON`).

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

### Two mechanisms worth understanding

- **Deduplication.** `filter_new()` drops what's already stored *and* what's
  duplicated inside the current batch (same article via two sources). Run the
  pipeline twice in a row → the second run reports "nothing new".
- **Mark-seen ordering.** `mark_seen()` runs **only after** `deliver_email.send()`
  succeeds. A crash mid-run leaves items unmarked, so the next run re-collects them
  — you never silently lose news.

---

## 6. Dev vs. prod mode (`APP_ENV`)

The fallbacks (raw list, local file) make dev frictionless but would let a
misconfigured cloud routine run "green" forever while silently doing nothing. So:

| Situation | `APP_ENV=dev` (local) | `APP_ENV=prod` (cloud) |
|-----------|----------------------|------------------------|
| No Claude key | raw-list fallback + notice | ❌ exit non-zero, nothing runs |
| No real email backend | writes `last_digest.md` | ❌ exit non-zero |
| `EMAIL_TO` missing | writes `last_digest.md` | ❌ exit non-zero |
| Key/API invalid at call time | fallback + message | ❌ raises (non-zero exit) |
| Backend resolves to SMTP | silent | ⚠️ loud warning (often blocked in cloud) |

`pipeline.preflight()` runs first and, in prod, **fails loudly** listing exactly
what's missing.

> A "green" cloud run only means "no infra error", **not** "the task succeeded".
> `APP_ENV=prod` is what turns a silent misconfig into a visible red run.

---

## 7. Email delivery

`deliver_email.resolve_backend()` picks a backend from config (`EMAIL_BACKEND`,
default `auto`): **resend → brevo → smtp → file**.

| Backend | Transport | Notes |
|---------|-----------|-------|
| `resend` | HTTPS 443 | Cloud-safe. Requires a verified domain (or `onboarding@resend.dev` for tests). |
| `brevo` | HTTPS 443 | Cloud-safe. Single-sender verification works without a domain. **Used here.** |
| `smtp` | 25/587 | Fine locally; often blocked in cloud sandboxes. |
| `file` | — | Writes `last_digest.md`. Dev fallback only. |

**Sender must be verified** with the provider, or the API rejects the send.

---

## 8. Sources (RSS & Hacker News)

Both are **free, no authentication**. Default sources are **French**.

```yaml
# sources.yaml
categories:
  ia:
    label: "🤖 Intelligence Artificielle"
    rss:
      - https://www.actuia.com/feed/
      - https://www.lebigdata.fr/feed
    # hn_query: "AI OR LLM OR GPT"   # Hacker News is English-only; uncomment to add
  dev:
    label: "💻 Développement & Tech"
    rss:
      - https://www.numerama.com/feed/
      - https://next.ink/feed/
      - https://www.lemondeinformatique.fr/flux-rss/thematique/toutes-les-actualites/rss.xml
```

Add a feed = add a URL. To preview what a feed yields before committing:
`python preview.py ia`. RSS maps `<title>→title`, `<link>→url`, `<pubDate>→published`,
`<description>→summary`, `<guid>→id`.

---

## 9. Local setup & run

```powershell
# install deps into the venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# create your local secrets file
Copy-Item .env.example .env   # then fill it in
```

```ini
# .env (local) — gitignored
APP_ENV=dev
ANTHROPIC_API_KEY=sk-ant-...        # local name is fine here
ANTHROPIC_MODEL=claude-opus-4-8
EMAIL_BACKEND=auto
BREVO_API_KEY=xkeysib-...
EMAIL_FROM=you@example.com
EMAIL_TO=you@example.com
SUPABASE_URL=https://xxxx.supabase.co   # omit both to use the local JSON backend
SUPABASE_KEY=sb_secret_...
```

```powershell
# run it (PYTHONUTF8=1 avoids the Windows cp1252 console choking on emojis)
$env:PYTHONUTF8=1
.\.venv\Scripts\python.exe pipeline.py
```

**Replay tip (local JSON backend):** clear the memory with
`Remove-Item state\seen.json`. **Supabase backend:** clear rows in the
`seen_items` table.

---

## 10. Cloud deployment (the routine)

Set up at **[claude.ai/code/routines](https://claude.ai/code/routines)** (requires
GitHub connected at [claude.ai/code](https://claude.ai/code) first).

1. **Connect GitHub** and grant access to the `watchtower` repo.
2. **Create a cloud environment** (`veille`):
   - **Environment variables** (`.env` format, no quotes):
     ```
     VEILLE_ANTHROPIC_API_KEY=sk-ant-...
     BREVO_API_KEY=xkeysib-...
     SUPABASE_URL=https://xxxx.supabase.co
     SUPABASE_KEY=sb_secret_...
     APP_ENV=prod
     ```
   - **Setup script:** `pip install -r requirements.txt`
   - **Network access:** Custom + `api.anthropic.com`, `api.brevo.com`, your
     Supabase host (keep package managers checked), or **Full**.
3. **Create the routine:** repo `watchtower`, environment `veille`, a small model,
   a **Daily** schedule, and the prompt:
   ```
   From the watchtower repo root, run: python pipeline.py
   Do not modify files, do not create commits or PRs.
   Report whether the digest was sent ("[email] envoyé via brevo") or the error.
   ```
4. **Run now** to test, then open the session to read the transcript.

Minimum routine interval is 1 hour; daily is fine. Runs draw down your subscription
usage plus a daily routine-run cap.

---

## 11. Feedback loop

Steer the next summary without touching code:

- **Local backend:** write a line into `state/feedback.md`.
- **Supabase backend:** insert a row into the `feedback` table
  (`note = "focus more on open-source model releases"`).

On the next run, `pending_feedback()` reads it, passes it into the Claude prompt,
then `mark_feedback_applied()` marks it so it's applied exactly once.

---

## 12. Feature status

| Feature | Status |
|---------|--------|
| RSS + Hacker News collection (French sources) | ✅ working |
| Deduplication | ✅ working (local + Supabase) |
| Claude summarization | ✅ working (needs API credits; dev falls back to a list) |
| Email delivery | ✅ working via Brevo |
| Supabase state | ✅ working |
| Dev/prod preflight | ✅ working |
| Cloud routine (laptop-off) | ⚙️ configured via claude.ai/code/routines |

---

## 13. Security notes

- `.env` is gitignored and never committed; only `.env.example` (empty template) is
  tracked. Verify with `git check-ignore .env`.
- Cloud environment variables are visible to anyone who can edit that environment —
  fine for a personal account, but don't share the environment.
- Rotate any key that has been pasted into a chat or shared.
- The Supabase **secret** key (`sb_secret_…`) is server-side only — never expose it
  client-side.

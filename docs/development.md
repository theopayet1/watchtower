# Development

## Project layout

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
├── digests/             ← generated locally: one .md per run (dev backend only)
└── last_digest.md       ← generated: email fallback output when no backend is set
```

### File responsibilities

| File | Role |
|------|------|
| `config.py` | Loads `.env` + `sources.yaml`. Exposes keys, `APP_ENV`/`IS_PROD`. Paths resolved relative to the file, so it works regardless of the working directory (cloud-safe). |
| `sources.yaml` | Categories, RSS feeds, HN keywords. **The only file you touch day to day.** |
| `collect/rss.py` | `feedparser` reads any feed; filters by date with `calendar.timegm` (UTC-correct) and decodes HTML entities. |
| `collect/hackernews.py` | HN Algolia API, filters by freshness server-side. No key. |
| `state.py` | Memory between runs. Same interface, two backends (local JSON / Supabase). |
| `synthesize.py` | Builds the prompt, calls Claude. Falls back to a markdown list if no key (dev only). |
| `deliver_email.py` | Picks an email backend and sends. Falls back to `last_digest.md` (dev only). |
| `pipeline.py` | The orchestrator + the `preflight()` check. |
| `preview.py` | Read-only: prints collected items without touching state. |

---

## Local setup & run

```powershell
# install deps into the venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# create your local secrets file
Copy-Item .env.example .env   # then fill it in
```

```ini
# .env (local) — gitignored
APP_ENV=dev
ANTHROPIC_API_KEY=sk-ant-...        # local name is fine
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

See [configuration.md](configuration.md) for every variable.

---

## Previewing collection

`preview.py` is read-only — it shows what the collectors return **without**
deduplication, summarization, email, or touching state. Run it as often as you
like, e.g. to test a new feed before adding it to `sources.yaml`.

```powershell
.\.venv\Scripts\python.exe preview.py        # all categories
.\.venv\Scripts\python.exe preview.py ia     # one category
```

---

## Replaying a run

Deduplication makes a second run report "nothing new". To force fresh items:

- **Local JSON backend:** `Remove-Item state\seen.json`
- **Supabase backend:** delete the rows in the `seen_items` table.

---

## Feedback loop

Steer the next summary without touching code:

- **Local backend:** write a line into `state/feedback.md`.
- **Supabase backend:** insert a row into the `feedback` table, e.g.
  `note = "focus more on open-source model releases"`.

On the next run, `pending_feedback()` reads it, passes it into the Claude prompt,
then `mark_feedback_applied()` marks it so it's applied exactly once.

---

## Adding a new source

1. Create `collect/yoursource.py` with a `collect(...)` function that returns a
   list of items in the [common item format](architecture.md#the-common-item-format-the-glue).
2. Wire it into `collect_category()` in `pipeline.py`.
3. Add its config under each category in `sources.yaml`.

Nothing else changes — dedup, summary, and delivery already handle any item.

# 🗞️ Automated Watch (Veille automatisée)

A small, dependency-light pipeline that **collects news from RSS feeds and Hacker
News by category, removes what you've already seen, has Claude summarize it, and
emails you a daily digest**.

It is designed to be runnable **right now with zero API keys** (it degrades
gracefully), then "lights up" feature by feature as you add credentials. The end
goal is to run it unattended as a scheduled **Claude Code remote routine** (cloud,
laptop closed).

---

## 1. What it does (data flow)

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
            state.filter_new()      ── drop anything already seen (state/seen.json)
                     ▼
            synthesize.synthesize() ── Claude summarizes (or raw list if no key)
                     ▼
            deliver_email.send()    ── email (or local file if no SMTP)
                     ▼
            state.mark_seen()       ── mark as seen, AFTER successful delivery
```

The key idea: **the pipeline knows nothing about the details of each source.** It
calls each collector, gets back a list of items in the **same shape**, then chains
dedup → summarize → deliver. Adding a new source later (YouTube, Bluesky, …) means
writing one new `collect/xxx.py` that returns that shape — nothing else changes.

---

## 2. The common "item" format (the glue of the whole system)

Every collector, whatever the source, returns a list of identical dictionaries:

```python
{
    "id":        "hn:43821",          # UNIQUE id → used for deduplication
    "source":    "Hacker News",       # shown in the digest
    "title":     "...",
    "url":       "https://...",
    "score":     128,                 # points / upvotes (None if not applicable)
    "published": "2026-06-12T...",    # ISO date or epoch
    "summary":   "..."                # optional excerpt
}
```

This contract is what lets `state.py`, `synthesize.py` and `deliver_email.py`
process RSS or Hacker News items without ever knowing where they came from. The
`id` prefix (`rss:`, `hn:`) prevents collisions between sources.

---

## 3. Project layout

```
PythonProject/
├── pipeline.py          ← entry point — this is what you run
├── config.py            ← loads .env + sources.yaml (single source of keys)
├── sources.yaml         ← YOUR editable config: categories, feeds, keywords
├── state.py             ← persistence: dedup, digest history, feedback
├── synthesize.py        ← builds the prompt + calls Claude (fallback: raw list)
├── deliver_email.py     ← SMTP send (fallback: writes last_digest.md)
├── requirements.txt
├── .env.example         ← template for your secrets (copy to .env)
├── .gitignore
├── collect/             ← one module per source
│   ├── __init__.py
│   ├── rss.py           ← any RSS/Atom feed (no key)
│   └── hackernews.py    ← Hacker News via the Algolia API (no key)
├── state/               ← generated at runtime
│   ├── seen.json        ← the dedup memory
│   └── feedback.md      ← drop a line here to steer the next summary
├── digests/             ← generated: one .md per run (history)
└── last_digest.md       ← generated: fallback output when no SMTP is set
```

### File responsibilities

| File | Role |
|------|------|
| `config.py` | Loads `.env` + `sources.yaml`. **Single entry point for keys.** Paths are resolved relative to the file, so it works even when the working directory changes (cloud). |
| `sources.yaml` | Your editable config: categories, RSS feeds, HN keywords. **The only file you touch day to day.** |
| `collect/rss.py` | `feedparser` reads any feed. Filters by date with `calendar.timegm` (**not** `mktime` — feedparser returns UTC dates; `mktime` would read them as local time and shift by hours). |
| `collect/hackernews.py` | HN Algolia API. `numericFilters=created_at_i>...` filters by freshness server-side. No key. |
| `state.py` | Memory between runs: `seen.json` (dedup), `digests/` (history), `feedback.md` (your notes). |
| `synthesize.py` | Builds the prompt, calls Claude. **Falls back** to a markdown list if no key. |
| `deliver_email.py` | SMTP `starttls`. **Falls back** to writing `last_digest.md` if no credentials. |
| `pipeline.py` | The orchestrator. This is what you run (`python pipeline.py`). |

---

## 4. Two mechanisms worth understanding

### Deduplication (`state.py`)
`filter_new()` does two things: it drops what is already in `seen.json` (seen on a
previous run) **and** what is duplicated within the current batch (same article
pulled by two sources). Run the pipeline twice in a row and the second run prints
"rien de nouveau" everywhere — that's dedup working.

### "Mark seen AFTER delivery" ordering (`pipeline.py`)
`state.mark_seen(all_new)` only runs **after** `deliver_email.send()`. If the
program crashes during summarization or sending, nothing is marked seen, so the
next run picks the news back up — you never silently lose items.

---

## 5. Sources: RSS & Hacker News

Both are **free and need no authentication**.

### RSS — you just consume feeds sites already publish
An RSS feed is a standardized XML file the site regenerates on every new post.
Each `<item>` is an article with stable tags:

| XML tag | Maps to |
|---------|---------|
| `<title>` | `title` |
| `<link>` | `url` |
| `<pubDate>` | `published` (drives the freshness filter) |
| `<description>` | `summary` |
| `<guid>` | `id` |

Unlike scraping (which is often against a site's terms), an RSS feed is *published
on purpose* for programs to read. To find a site's feed, try `/feed`, `/rss`,
`/feed.xml`, or look in the page source for `<link type="application/rss+xml">`.
YouTube channels and Reddit subreddits also expose feeds
(`reddit.com/r/<sub>/.rss`).

**To add a source, just add a URL — no code change:**
```yaml
  ia:
    label: "🤖 Intelligence Artificielle"
    rss:
      - https://huggingface.co/blog/feed.xml
      - https://www.technologyreview.com/feed/
      - https://your-new-feed.com/feed     # ← add here
```

### Hacker News — full-text search via the Algolia API
`hn_query` is a plain-text search; the collector asks Algolia for `story` items
newer than `freshness_hours`.

---

## 6. Setup

```powershell
# from the project root, with the venv's python
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Dependencies: `requests`, `feedparser`, `PyYAML`, `python-dotenv` (always needed);
`anthropic` (only for real Claude summaries); `supabase` (only for cloud state,
commented out for now).

Copy the secrets template and fill in what you have (everything is optional thanks
to the fallbacks):
```powershell
Copy-Item .env.example .env
```

```ini
# .env
ANTHROPIC_API_KEY=        # enables real Claude summaries
ANTHROPIC_MODEL=claude-opus-4-8
SMTP_HOST=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USER=               # your mailbox
SMTP_PASSWORD=           # app password (NOT your account password)
EMAIL_FROM=theogame36@outlook.fr
EMAIL_TO=theogame36@outlook.fr
```

---

## 7. Run it

```powershell
# PYTHONUTF8=1 avoids the Windows cp1252 console choking on emojis/accents
$env:PYTHONUTF8=1
.\.venv\Scripts\python.exe pipeline.py
```

What you'll see: each category is collected, deduped, summarized, then the digest
is delivered (emailed, or written to `last_digest.md` if no SMTP).

### Testing tip — replay as if it were brand new
Dedup will say "nothing new" on a second run. To force fresh items, clear the
memory:
```powershell
Remove-Item state\seen.json
```

---

## 8. Feature status

| Feature | Status | To enable |
|---------|--------|-----------|
| RSS, Hacker News, dedup, pipeline | ✅ working for real | nothing |
| Claude summary | fallback (raw list) active | set `ANTHROPIC_API_KEY` + `pip install anthropic` |
| Email | fallback (local file) active | set a Resend/Brevo API key (cloud-safe) or SMTP (local only) |
| State | local JSON (`state/seen.json`) | fine for dev; swap to Supabase for cloud |

> ⚠️ **Email delivery & the cloud.** SMTP egress (ports 25/587) is frequently
> blocked inside remote-routine sandboxes for anti-spam reasons — even on a "Full"
> network that only allows HTTPS 443. So SMTP can work locally and **fail silently
> in the cloud** with correct credentials. For the routine, use an HTTP email API
> (Resend or Brevo, REST over HTTPS 443). `deliver_email.py` picks the backend via
> `EMAIL_BACKEND` (`auto` → resend → brevo → smtp → file); keep SMTP for local dev,
> set a Resend/Brevo key for the cloud.

> ⚠️ **Silent fallbacks vs. production.** A "green" cloud run only means "no infra
> error", not "the task succeeded". The dev fallbacks (raw list, local file) are
> great locally but would let a misconfigured routine run green every day while
> really just writing `last_digest.md`. Set **`APP_ENV=prod`** in the routine: the
> pipeline then runs a **preflight** and **fails loudly** (non-zero exit → red run)
> if `ANTHROPIC_API_KEY` or a real email backend is missing, instead of degrading
> silently.

---

## 9. Feedback loop

The watch can be steered without touching code. Write a line into
`state/feedback.md`, e.g.:

```
Focus more on open-source model releases; keep each point to one sentence.
```

On the next run, `pipeline.py` reads it via `state.pending_feedback()`, passes it
into the Claude prompt, then `state.mark_feedback_applied()` archives it so it's
applied exactly once.

---

## 10. Roadmap → fully autonomous (cloud, laptop closed)

The pipeline is stateless-friendly by design. To run it as a **Claude Code remote
routine** (runs in Anthropic's cloud on a schedule, even with your machine off):

1. **Swap state to Supabase.** Remote routines run in a fresh, ephemeral
   environment each time, so `seen.json` on disk wouldn't persist. `state.py`
   keeps the same interface (`filter_new` / `mark_seen` / …) precisely so only the
   internals change.
2. **Push the repo to GitHub.** The routine clones it on each run.
3. **Set the keys as routine environment variables** (a local `.env` never reaches
   the cloud).
4. **Create the routine** with a daily trigger pointing at `python pipeline.py`.

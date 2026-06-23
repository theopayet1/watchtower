# 🗞️ Watchtower — Automated News Watch

A small, dependency-light pipeline that **collects news by category (RSS + Hacker
News), removes what you've already seen, has Claude summarize it, and emails you a
daily digest** — in English.

It runs locally for development and, in production, as a **scheduled Claude Code
cloud routine** on Anthropic's infrastructure: daily, **even with your laptop
closed**.

```
sources.yaml ─► collect (RSS + Hacker News) ─► dedup ─► Claude summary ─► email digest
                                                 ▲                          │
                                          Supabase (state) ◄────────────────┘
```

---

## Quickstart (local)

```powershell
# 1. install dependencies into the venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. create your local secrets file, then fill it in
Copy-Item .env.example .env

# 3. run it
$env:PYTHONUTF8=1
.\.venv\Scripts\python.exe pipeline.py
```

With no keys configured it still runs end-to-end (raw-list summary, digest written
to `last_digest.md`). Add an Anthropic key for real summaries and a Brevo key to
send email. Preview what the collectors return without sending anything:

```powershell
.\.venv\Scripts\python.exe preview.py        # all categories
.\.venv\Scripts\python.exe preview.py ia     # one category
```

---

## Documentation

| Doc | What's inside |
|-----|---------------|
| [docs/architecture.md](docs/architecture.md) | Pipeline data flow, **cloud + database architecture diagrams**, the item format, state backends and the Supabase data model |
| [docs/configuration.md](docs/configuration.md) | `sources.yaml`, every environment variable, dev/prod modes, email backends |
| [docs/development.md](docs/development.md) | Project layout, file responsibilities, local run, preview, the feedback loop |
| [docs/deployment.md](docs/deployment.md) | Setting up the cloud routine, network allowlist, the reserved env-var gotcha, security |

---

## How it fits together (short version)

```
GitHub repo (code, no secrets)
      │ cloned each run
      ▼
Claude Code cloud routine ──► RSS + Hacker News   (collect)
  secrets via env vars   ──► Supabase             (dedup / history / feedback)
  pip install + run      ──► Claude API           (summary)
                         ──► Brevo API (HTTPS)     (email) ──► 📧 inbox
```

Full version with the reasoning behind each external service:
[docs/architecture.md](docs/architecture.md).

---

## Feature status

| Feature | Status |
|---------|--------|
| RSS + Hacker News collection | ✅ working |
| Deduplication (local + Supabase) | ✅ working |
| Claude summarization | ✅ working (needs API credits; dev falls back to a list) |
| Email delivery (Brevo, HTTPS) | ✅ working |
| Supabase state | ✅ working |
| Dev/prod preflight (fail-loud) | ✅ working |
| Cloud routine (laptop-off) | ⚙️ via [claude.ai/code/routines](https://claude.ai/code/routines) — see [deployment](docs/deployment.md) |

---

## Tech stack

Python 3.13 · `requests` · `feedparser` · `PyYAML` · `python-dotenv` ·
`anthropic` (Claude API) · `supabase` (PostgreSQL) · Brevo (email over HTTP).

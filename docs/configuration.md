# Configuration

## `sources.yaml`

Your editable config: global settings, then one entry per category. All source
fields are optional — omit one and its collector is skipped.

```yaml
max_per_source: 15        # max items fetched per source, per category
freshness_hours: 30       # ignore anything older than this (RSS / Hacker News)

categories:
  ia:
    label: "🤖 Artificial Intelligence"
    rss:
      - https://huggingface.co/blog/feed.xml
      - https://www.technologyreview.com/feed/
    hn_query: "AI OR LLM OR GPT"     # Hacker News full-text search (Algolia)
  dev:
    label: "💻 Development & Tech"
    rss:
      - https://techcrunch.com/feed/
      - https://www.theverge.com/rss/index.xml
    hn_query: "python OR rust OR javascript OR framework"
```

- **`label`** shows up as the section header in the digest.
- **`rss`** — any RSS/Atom feed URL, no key. To find a site's feed try `/feed`,
  `/rss`, `/feed.xml`, or look in the page source for
  `<link type="application/rss+xml">`.
- **`hn_query`** — plain-text Hacker News search; only `story` items newer than
  `freshness_hours` are returned.

Add a source = add a URL. Preview before committing: `python preview.py ia`.

---

## Environment variables (`.env` locally, routine env in the cloud)

Copy `.env.example` to `.env` for local dev (it's gitignored). In the cloud, set
these in the routine's environment instead — see [deployment.md](deployment.md).

| Variable | Required | Purpose |
|----------|----------|---------|
| `APP_ENV` | recommended | `dev` (silent fallbacks) or `prod` (fail loud). Default `dev`. |
| `ANTHROPIC_API_KEY` | for summaries (local) | Claude API key. **In the cloud use `VEILLE_ANTHROPIC_API_KEY`** (see below). |
| `VEILLE_ANTHROPIC_API_KEY` | for summaries (cloud) | Same key, non-reserved name. `config.py` reads this first, falls back to `ANTHROPIC_API_KEY`. |
| `ANTHROPIC_MODEL` | optional | Defaults to `claude-opus-4-8`. Set `claude-haiku-4-5` for lower cost. |
| `EMAIL_BACKEND` | optional | `auto` (default) / `resend` / `brevo` / `smtp` / `file`. |
| `BREVO_API_KEY` | for email | Brevo HTTP API key (`xkeysib-…`). |
| `RESEND_API_KEY` | alt. email | Resend HTTP API key. |
| `SMTP_HOST/PORT/USER/PASSWORD` | alt. email | SMTP credentials (local only — often blocked in cloud). |
| `EMAIL_FROM` / `EMAIL_TO` | for email | Sender (must be verified with the provider) and recipient. |
| `SUPABASE_URL` / `SUPABASE_KEY` | for cloud state | Project URL + **secret** key (`sb_secret_…`). Omit both to use the local JSON backend. |

> **Why `VEILLE_ANTHROPIC_API_KEY`?** On Claude Code cloud, `ANTHROPIC_API_KEY` is
> reserved by the platform and is not passed to your script. The custom name avoids
> that. Locally, either name works.

---

## Dev vs. prod mode (`APP_ENV`)

The fallbacks (raw list, local file) make dev frictionless but would let a
misconfigured cloud routine run "green" forever while silently doing nothing.
`pipeline.preflight()` runs first and, in prod, **fails loudly**.

| Situation | `APP_ENV=dev` | `APP_ENV=prod` |
|-----------|---------------|----------------|
| No Claude key | raw-list fallback + notice | ❌ exit non-zero, nothing runs |
| No real email backend | writes `last_digest.md` | ❌ exit non-zero |
| `EMAIL_TO` missing | writes `last_digest.md` | ❌ exit non-zero |
| Key/API invalid at call time | fallback + message | ❌ raises (non-zero exit) |
| Backend resolves to SMTP | silent | ⚠️ loud warning (often blocked in cloud) |

> A "green" cloud run only means "no infra error", **not** "the task succeeded".
> `APP_ENV=prod` is what turns a silent misconfig into a visible red run.

---

## Email backends

`deliver_email.resolve_backend()` picks from `EMAIL_BACKEND` (default `auto`):
**resend → brevo → smtp → file**.

| Backend | Transport | Notes |
|---------|-----------|-------|
| `resend` | HTTPS 443 | Cloud-safe. Requires a verified domain (or `onboarding@resend.dev` for tests). |
| `brevo` | HTTPS 443 | Cloud-safe. Single-sender verification works without a domain. **Used here.** |
| `smtp` | 25/587 | Fine locally; often blocked in cloud sandboxes. |
| `file` | — | Writes `last_digest.md`. Dev fallback only. |

The **sender** (`EMAIL_FROM`) must be verified with the provider, or the API
rejects the send.

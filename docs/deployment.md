# Deployment — the cloud routine

Run the watch unattended on Anthropic's infrastructure (laptop closed) with a
**Claude Code cloud routine**. Set up at
[claude.ai/code/routines](https://claude.ai/code/routines). Requires a Claude
Pro/Max/Team plan with Claude Code on the web enabled.

## 1. Connect GitHub

First connect GitHub at [claude.ai/code](https://claude.ai/code) (the "Connect
GitHub" prompt installs the Claude GitHub App). Grant it access to the
`watchtower` repo (or all repos). Until this is done, the repo won't appear in the
routine's repository picker.

## 2. Create a cloud environment

In the environment settings:

- **Environment variables** (`.env` format, **no quotes**):
  ```
  VEILLE_ANTHROPIC_API_KEY=sk-ant-...
  BREVO_API_KEY=xkeysib-...
  EMAIL_FROM=you@verified-sender.com
  EMAIL_TO=you@example.com
  SUPABASE_URL=https://xxxx.supabase.co
  SUPABASE_KEY=sb_secret_...
  APP_ENV=prod
  ```
  `EMAIL_FROM` must be a sender you verified with Brevo; `EMAIL_TO` is the
  recipient. Without them the `prod` preflight fails ("EMAIL_TO missing") and Brevo
  rejects a send with no sender.
- **Setup script:**
  ```
  pip install -r requirements.txt
  ```
- **Network access:** `Custom` + keep package managers checked + add:
  ```
  api.anthropic.com
  api.brevo.com
  <your-project>.supabase.co
  ```
  (or use `Full` to start).

## 3. Create the routine

- **Repository:** `watchtower`
- **Environment:** the one created above
- **Model:** a small one (the routine just runs a script)
- **Schedule:** `Daily` at your chosen time (minimum interval is 1 hour)
- **Prompt:**
  ```
  From the watchtower repo root, run: python pipeline.py
  Do not modify files, do not create commits or PRs.
  Report whether the digest was sent ("[email] envoyé via brevo") or the error.
  ```

## 4. Test

Click **Run now**, then open the session and read the transcript.

- ✅ green run **and** email received → autonomy achieved.
- ❌ error → the `APP_ENV=prod` preflight prints exactly what's missing.

---

## Gotchas (these cost real debugging time)

### A "green" run is not success
A green status only means the session started and exited without an infrastructure
error. It does **not** mean the task succeeded. Open the transcript to confirm.
This is exactly why `APP_ENV=prod` exists — it turns a silent misconfig into a
non-zero exit (red run).

### `ANTHROPIC_API_KEY` is reserved in the cloud
Claude Code cloud reserves that name and does not pass it to your script. Use
**`VEILLE_ANTHROPIC_API_KEY`** — `config.py` reads it first and falls back to
`ANTHROPIC_API_KEY` locally.

### Network allowlist blocks outbound calls
The default environment blocks non-allowlisted domains (`403 host_not_allowed`).
Brevo and Supabase calls fail unless you add `api.brevo.com` and your Supabase host
(and `api.anthropic.com`) to **Allowed domains**, or use `Full`. Note: choosing
Brevo over SMTP solves the *port* problem, but the domain still has to be allowed.

### SMTP is often blocked
SMTP egress (25/587) is frequently blocked in cloud sandboxes. Always use an HTTP
email API (Brevo/Resend) for the routine.

### Supabase free projects can pause
A free-tier Supabase project can be paused (its `*.supabase.co` host stops
resolving → `getaddrinfo failed`). If a run fails on DNS, check the project is
active in the Supabase dashboard and click **Restore**.

---

## Security

- `.env` is gitignored and never committed; only `.env.example` (empty template) is
  tracked. Verify with `git check-ignore .env`.
- Cloud environment variables are visible to anyone who can edit that environment —
  fine for a personal account, but don't share the environment.
- Rotate any key that has been pasted into a chat or otherwise exposed.
- The Supabase **secret** key (`sb_secret_…`) is server-side only — never expose it
  client-side.

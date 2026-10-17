# forgejo-kanboard-bridge

One-way mirror: **Forgejo issue events → Kanboard tasks**. Forgejo stays the
authoritative repo tracker; Kanboard is the single-pane-of-glass view across
projects (plus non-code cards that never touch Forgejo).

## What it does

- Per-repo Forgejo webhooks (`issues` events) POST to this service on
  `phantomlink`; HMAC-SHA256 signature verified against `FORGEJO_WEBHOOK_SECRET`.
- `opened`/`edited` → create or update a Kanboard card titled
  `repo#N: <title>`, with the issue URL in the description and
  `reference = forgejo:<repo>#<N>` (this is the dedup key — repeated events and
  re-syncs do not duplicate).
- `closed` → `closeTask` (card leaves the board). `reopened` → card reopens in
  the first column.
- `POST /sync` — backfill: mirrors every open issue on every `nic/*` repo.
- Repo → board routing via `REPO_MAP` (JSON `glob → project_id`); unmatched
  repos land in `DEFAULT_PROJECT` (Dev, id 11).

## Deploy

```bash
cp .env.example .env   # fill in tokens + webhook secret
docker --context ghost compose -f compose/ghost/forgejo-kanboard-bridge/docker-compose.yml up -d --build
```

Env vars: `KANBOARD_URL`, `KANBOARD_TOKEN` (jsonrpc user token,
`~/.local/share/devin/kanboard-token`), `FORGEJO_API_URL`, `FORGEJO_TOKEN`
(`~/.local/share/devin/forgejo-token`), `FORGEJO_WEBHOOK_SECRET`, `REPO_MAP`,
`DEFAULT_PROJECT`.

## Webhooks

User-level hooks need a Forgejo token with `write:user` scope — our token
doesn't have it, so hooks are **per-repo** instead. Created over the API:

```bash
POST /api/v1/repos/<owner>/<repo>/hooks
{"type":"forgejo","active":true,"events":["issues"],
 "config":{"url":"http://forgejo-kanboard-bridge:8077/",
           "content_type":"json","secret":"<FORGEJO_WEBHOOK_SECRET>",
           "http_method":"post"}}
```

New repos created later need the same hook (or re-run a loop over
`GET /api/v1/users/nic/repos`).

### Gotchas (hit 2026-10-07)

1. **`webhook.ALLOWED_HOST_LIST`** — Forgejo refuses to deliver to private
   IPs/container names by default. `compose/ghost/forgejo/docker-compose.yml`
   sets `FORGEJO__webhook__ALLOWED_HOST_LIST=forgejo-kanboard-bridge`.
   Symptoms without it: hook task rows in sqlite show
   `webhook can only call allowed HTTP servers`.
2. **The API silently drops `config.secret`** on PATCH — the hook's `secret`
   column stays empty and Forgejo sends `X-Forgejo-Signature:` blank.
   Fixed by direct sqlite update:

   ```bash
   ssh ghost python3 -c "
   import sqlite3
   db = sqlite3.connect('/tank/encrypted/docker/forjeo-zfs/forgejo/data/gitea.db')
   db.execute(\"update webhook set secret='<FORGEJO_WEBHOOK_SECRET>' \
               where url like '%forgejo-kanboard-bridge%'\"); db.commit()"
   ```

   If a hook is created via the API with `config.secret` included it may
   persist — verify with the sqlite query above if signatures come up empty.

## Debugging

- Bridge logs: `docker --context ghost logs forgejo-kanboard-bridge`
  (prints each event's `action repo#N -> result` and rejected signatures).
- Deliveries live in sqlite, not the API:
  `hook_task` table — `request_content`/`response_content` show exactly what
  was sent/returned.
- `GET /api/v1/repos/<o>/<r>/hooks/<id>/tests` doesn't exist; use
  `POST .../hooks/<id>/tests` to enqueue a test delivery.

## Verification (done 2026-10-07)

- Backfill `/sync` created 17 cards (homelab-mono #1–11, notifiq, pype.dev).
- Live flow: edit `nic/digital-harbor-ops#1` → card 433 created on the
  Digital Harbor board; close issue → card closed (`is_active=0`);
  duplicate deliveries dedup via `reference`.

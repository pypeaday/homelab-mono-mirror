# Twenty CRM

Personal CRM at https://crm.paynepride.com — contacts, companies, pipeline,
notes/tasks per record. Used for client sites, prospects, and nonprofit work.

## Deploy

```bash
cd ~/projects/personal/homelab-mono/compose/ghost/twenty
docker --context ghost compose up -d
```

- Secrets in `.env` (gitignored): `PG_DATABASE_PASSWORD`, `ENCRYPTION_KEY`
  (losing it loses every stored secret — OAuth tokens, API creds).
- Data on ghost: `/tank/encrypted/docker/twenty/{db,server}`
- Image pinned via `TAG` in `.env` — bump deliberately, migrations run on
  server boot. First boot takes several minutes (full migration chain);
  healthcheck flips healthy only after `/healthz` returns 200.

## Agent access

Twenty exposes REST (`/rest/*`) and GraphQL (`/graphql`) — same auth:

```
Authorization: Bearer <api-key>
```

Create a key in the UI: **Settings → APIs & Webhooks → API Keys**.
OpenAPI metadata lives at `/open-api/core` and `/open-api/metadata`.

Devin agents get it as an MCP server: `~/.config/devin/mcp_config.json`
(user scope, `twenty` entry, `/mcp` streamable HTTP) with the key read from
`~/.local/share/devin/twenty-api-key` via `${file:}` expansion — same
convention as `forgejo-token`. Tools allowlisted via `mcp__twenty__*` in
`config.json` permissions.

## Gotchas

- **Service names are prefixed `twenty-` on purpose.** The shared
  `phantomlink` network resolves bare names like `db`/`redis` to *other
  projects'* containers (e.g. `forjeo-db-1`). First deploy failed auth because
  `db` hit a foreign postgres. Keep prefixes if editing.
- Backup: `docker exec twenty-db pg_dump -U postgres default > backup.sql`
  (or add to the restic/docker backup flow — not wired yet).
- No SMTP configured — password signup/login works; email invites and
  notification emails won't send until `EMAIL_SMTP_*` vars are set.
- LAN access works via hairpin on the public A record; if that ever breaks,
  add a local record on the DNS box (192.168.1.4) → 192.168.1.9.
- **The live compose dir on ghost is
  `/tank/encrypted/nas/code/homelab-compose/ghost/twenty`** — the homelab-mono
  checkout went missing there (same story as homelab-stack); this repo dir is
  the source of truth, rsync it to ghost before `docker compose up -d`.
- `IS_MULTIWORKSPACE_ENABLED=true` set 2026-10-05 (in both `.env` copies) —
  enables the workspace switcher "Create workspace" flow; second workspace is
  for Good Works Power Washing.
- **Multi-workspace routing**: Twenty redirects base domain → `app.crm.paynepride.com`
  (sign-in) and serves each workspace at `<subdomain>.crm.paynepride.com`. Ghost's
  traefik is **v3** (compose tag lies) and never spawned the TLS router variant for
  this service — the working route is the **`twenty-crm` file-provider router**
  (entrypoint `websecure`, service `twenty@docker`).
  Entrypoint `tls.domains` in `traefik.toml` carries the `*.crm.paynepride.com` SAN
  (DNS wildcard already covers it). **When a workspace is created or renamed, add
  its `Host()` to the twenty-crm rule.**
- **Traefik mounts `/tank/encrypted/docker/traefik/config.yml`** — a separate file
  from this repo's `../traefik/private/config.yml` (and from the homelab-compose
  checkout copy). Edit the mounted file for live changes (in-place write, not
  `sed -i` — the single-file bind mount pins the inode) and mirror the edit in the
  repo copy. Workspace subdomains live in `core.workspace.subdomain` — rename via
  SQL (`update core.workspace set subdomain=...`) or Settings; current: `dh`
  (Digital Harbor), `gdwrks` (Good Works), `notifiq`.
- The SPA only responds to `Accept: text/html` requests — `curl` returns
  NestJS JSON 404s on app paths; test in a browser or with that header.

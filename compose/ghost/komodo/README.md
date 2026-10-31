# Komodo

Container/stack management on ghost. UI: https://komodo.paynepride.com (local auth; admin `nic`, creds in `.env` in this dir — aurora-side only, gitignored).

Deploy stack itself: `docker --context ghost compose -p komodo up -d`

## How stacks deploy

Komodo Stacks clone `nic/homelab-mono` into
`/tank/encrypted/docker/komodo-zfs/periphery/stacks/<stack-name>/` on ghost,
then run `compose/ghost/<stack>/docker-compose.yml` from the clone.

Deploy sequence per stack: **fresh clone → write `.env` → `compose config` → `up -d`**.

### .env gotcha (bit us 2026-10-11)

- `.env` is written **only** from the stack's *Environment* field in the Komodo
  UI (stored in mongo `Stack.config.environment`). Files placed in the clone
  dir by hand are wiped on reclone.
- A compose file declaring `env_file: .env` + empty Komodo Environment =
  `env file ... not found` deploy failure.
- Audit command: query mongo `Stack` for `env_file_path` set +
  `environment` empty + compose that declares `env_file:`.

## Rollout model (current)

`auto_pull`, `poll_for_updates`, `auto_update`, `webhook_force_deploy` are all
OFF. Renovate merges appear as "requires: Redeploy" but ship only on manual
**Pull → Deploy** in the UI. Auto-deploy policy decision tracked in kanboard
card 454.

## Renovate

`compose/ghost/renovate/` runs the self-hosted runner (scheduled, not
always-on); `renovate.json` at repo root groups update PRs per compose file.

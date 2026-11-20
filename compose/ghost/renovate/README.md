# Renovate

Scheduled, self-hosted [Renovate](https://docs.renovatebot.com/) run against
`nic/homelab-mono`. Opens one Forgejo PR per compose stack directory when an
image has a newer tag (e.g. "compose/ghost/arrs images"). No automerge —
PRs are reviewed and merged by hand.

## Layout

- `renovate.json` (repo root) — docker-compose manager only, per-directory
  grouping, digest-pinned images disabled (gluetun, netdata, glances,
  domain-locker, archivebox-telegram-bot, image_to_text_generator).
- `docker-compose.yml` — one-shot runner, `renovate/renovate:44.132.2`.
- `.env` — `RENOVATE_TOKEN` + `RENOVATE_*` runner vars (see `.env.example`).

## Manual run

```bash
cp .env.example .env   # fill in RENOVATE_TOKEN
docker --context ghost compose -f compose/ghost/renovate/docker-compose.yml run --rm renovate
```

## Scheduled run (ghost cron)

The repo isn't checked out on ghost, so cron calls `docker run` with an env
file on the host:

```bash
# on ghost, once:
sudo mkdir -p /tank/encrypted/docker/renovate
# copy this dir's .env there (RENOVATE_TOKEN must be set in it)

# crontab -e on ghost — nightly 04:30, logs to the stack dir
30 4 * * * docker run --rm --name renovate-run --env-file /tank/encrypted/docker/renovate/.env renovate/renovate:44.132.2 >> /tank/encrypted/docker/renovate/renovate.log 2>&1
```

## Notes

- First run opens many PRs (one per stack dir) — `prHourlyLimit` and
  `prConcurrentLimit` in renovate.json throttle them.
- The runner updates itself: `renovate/renovate` in this file is a
  docker-compose dep, so its bumps land in a "compose/ghost/renovate
  images" PR like any other stack.
- `.env` must exist both next to this file (for `compose run`) and at
  `/tank/encrypted/docker/renovate/.env` on ghost (for cron).

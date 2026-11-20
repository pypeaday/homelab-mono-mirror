# Traefik

reverse proxy

Need to make sure to scp the files in private to the server

## git-crawl router (2026-11-09, kanboard #514)

`git-crawl@file` in `private/config.yml` front-runs the docker `git` router on
`git.paynepride.com` for deep-browse paths (`src|commits|commit|blame|raw|
archive|media|find|compare|graph`) and caps them at 6 concurrent via
`inFlightReq` bucketed by `requestHost` — a *global* cap, because AI crawlers
rotate IPs (Alibaba 47.79/47.82 + residential pool) so per-IP limits are
useless. Git protocol (`info/refs`, `git-upload-pack`), `/api`, and repo-home
pages stay uncapped. Deployed by `scp`-ing config.yml only — file provider
hot-reloads, no traefik recreate needed. Same incident: `nic/{strudel,Bolt,
pyforgejo,delightful-forgejo}` (pull-mirrors, pure crawler bait, ~92% of anon
traffic) flipped private via Forgejo API. If crawlers pivot to public original
repos, the next lever is `FORGEJO__service__REQUIRE_SIGNIN_VIEW=true` in the
forgejo compose env (breaks anonymous https clone — LAN box 10.10.1.130 does
clone homelab-mono/notifiq that way and would need a token or ssh).

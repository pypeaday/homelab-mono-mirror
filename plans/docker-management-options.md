# Docker Management — Portainer Replacement Options

> Status: Research — awaiting decision
> Created: 2026-10-08

## Goal

Replace Portainer CE (`compose/ghost/portainer`, `portainer.paynepride.com`, agent on babyblue)
with something that gives **both a good web UI and terminal management (CLI/TUI) across all
hosts** — ghost (~120 containers / ~50 compose stacks), babyblue, ghost-vault, aurora — over the
Tailscale tailnet.

Compose files are the source of truth in this repo (`compose/<host>/<stack>/`), currently deployed
via `docker --context ghost compose up -d`.

## TL;DR ranking

| Rank | Tool | Multi-host | Compose + git | Terminal story | Web UI | Footprint | License | Health |
|---|---|---|---|---|---|---|---|---|
| 1 | **Komodo** | Periphery agent (outbound WS, unlimited) | ✅ 3 modes incl. git clone on host + push webhook | `km` CLI (deploy/ssh/exec/db) + REST/WS API | Excellent | Core + MongoDB/FerretDB + tiny agent | GPL-3.0 | 12.6k★, v2.3.3 Sep 2026, very active |
| 2 | **Arcane** | Agent per host (Direct :3553 or Edge outbound) | ✅ Git pull sync + push-backup, JSON bulk import | `arcane-cli` (full, `--json`) + REST API | Excellent | 1 container + sqlite, agent per host | BSD-3 | 7.8k★, v2.15.1 Oct 2026, extremely active |
| 3 | **Dockge + lazydocker** | Agent = another Dockge instance, primary proxies | File-based stacks dir; no git sync | lazydocker via `DOCKER_HOST=ssh://` | Good, minimal | ~1 container per host | MIT | 24.6k★, but last release 1.5.0 Mar 2025 |
| 4 | **Dockman** | SSH tunnels, agentless | File-first editor; no git sync | None (web only) | Good, keyboard-first | 1 container | AGPL-3.0 | 648★, v3.2.0 Feb 2026, young |
| 5 | **Sencho** | Peer nodes + Pilot Agent (outbound WS) | File-on-disk compose-first | None | Good | 1 container per node | AGPL-3.0 | 472★, pre-1.0, very new (Feb 2026) |
| 6 | **Dockpeek** | `DOCKER_HOST_N_*` socket proxies | ❌ read/deploy-light dashboard | None | Clean dashboard | 1 tiny container | MIT | 2.1k★, active |

Terminal-only (complements, not replacements): **lazydocker** (53k★, MIT, v0.25.2 Apr 2026),
**dry** (3.3k★, MIT, v0.13.0 Mar 2026, swarm-aware), **oxker** (1.9k★, MIT, `--host`/`$DOCKER_HOST`,
active), **ctop** (17.8k★, metrics-only, dormant — last push Jul 2024).

Not a fit: **Yacht**, **Runtipi**, **CasaOS**, **Cosmos** (details below).

---

## 1. Komodo — *recommended*

https://github.com/moghtech/komodo · https://komo.do/docs/intro

- **What**: hub-and-agent control plane for "build and deploy software on many servers". Rust,
  GPL-3.0, 12.6k★, latest v2.3.3 (2026-09-01), commits active (last push 2026-09-21).
- **Multi-host**: purpose-built. **Core** (API + web UI + DB) calls **Periphery**, a small stateless
  agent per server, over a bidirectional websocket — Periphery can dial *out* to Core, so NAT/tailnet
  hosts need no inbound port. Install via systemd script, docker container, or bare binary;
  onboarding keys + automatic key rotation; "no limit to the number of servers".
  (https://komo.do/docs/setup/connect-servers)
- **Compose + git**: the `Stack` resource supports three file modes — written in UI, **files on
  host**, or **git repo cloned onto the host** — with `git_provider` accepting arbitrary domains (not
  GitHub-only → Forgejo works), `repo`, `branch`, `run_directory`, multi-file `-f` support, `.env`
  generation with variable interpolation, and webhooks to auto-redeploy on push.
  **Imports existing compose projects by project name** — ghost's ~40 running stacks can be adopted
  without redeploying. (https://komo.do/docs/deploy/compose)
- **Terminal**: `km` CLI (linux/mac binaries, `ghcr.io/moghtech/komodo-cli`): `km deploy stack
  my-stack`, `km run action`, `km ssh <server>` (interactive shell via periphery), `km exec
  <container> bash`, `km attach`, `km set var`, `km db backup/restore`. Plus REST+WS API with Rust
  crate and NPM client. (https://komo.do/docs/ecosystem/cli)
- **Extras**: image builds (dockerfile in UI or git repo, remote builders), Procedures/Actions
  automation with scheduling, Resource Syncs (declarative TOML of all resources — itself
  commit-able to the monorepo for config GitOps), alerts, granular RBAC, OIDC, full audit trail,
  Docker Swarm support, browser terminals. (https://komo.do/docs/intro)
- **Footprint**: Core container + a database — **MongoDB is the recommended DB** (FerretDB/Postgres
  supported as an alternative for hosts that can't run modern Mongo). Periphery is a tiny static
  binary (~22MB download, idle-usage negligible). Honest cost: 2 infra containers on the core host
  vs Portainer's 1. (https://komo.do/docs/setup)
- **Caveats**: DB dependency is the main "weight"; feature surface is big (but modular — nothing to
  enable you don't use); GPL-3.0; self-hosts fine over tailnet.

## 2. Arcane — *strong runner-up, lightest full replacement*

https://github.com/getarcaneapp/arcane · https://getarcane.app/docs

- **What**: "Modern Docker Management" — Go backend + SvelteKit UI, BSD-3-Clause, 7.8k★, created Apr
  2025 and moving fast: v2.15.1 released 2026-10-07 (literally yesterday), commits same-day.
- **Multi-host**: **Remote Environments** — each remote host runs a small agent
  (`ghcr.io/getarcaneapp/agent`, mounts docker.sock). Two modes: **Direct** (manager→agent TCP 3553,
  fine on tailnet) and **Edge** (agent dials out to manager: poll / websocket / gRPC transport,
  optional mTLS) for NAT'd hosts. Also manages Docker Swarm clusters.
  (https://getarcane.app/docs/remote/environments.html)
- **Compose + git**: Projects = compose projects on disk (`PROJECTS_DIRECTORY`, e.g. a checkout of
  `compose/ghost/`). **Git Sync** per project: *Pull* (clone repo path → deploy; auto-sync interval,
  "pull image after sync", "redeploy after sync", sync-whole-folder for `include`/relative files) and
  *Push* (commit UI edits back to git, GPG signing, commit identity). Generic git auth (HTTP token or
  SSH key) → Forgejo-compatible. **Bulk JSON import** can create all ~40 pull syncs at once —
  each pointing at `compose/ghost/<name>/docker-compose.yml` in this repo. Pre-deploy lifecycle
  hooks. (https://getarcane.app/docs/docker/git-sync.html)
- **Terminal**: `arcane-cli` is a real CLI, not an afterthought: `auth login` (device flow),
  `environments switch` / per-command `--env`, `containers list/restart/update(s)`, `projects
  up/down/redeploy/destroy` (streams raw compose output), `gitops sync`, `images`, `volumes`,
  `system prune/upgrade/convert`, vuln scans, backups, webhooks, updater, `doctor`, `--output json`
  for scripting. (https://getarcane.app/docs/reference/cli/commands.html)
- **Extras**: OIDC/SSO, passkeys/MFA, RBAC, image vuln scanning, socket-proxy support, notifications,
  templates + registries, container updates (manual + scheduled auto-update), system backups to S3,
  mobile app.
- **Footprint**: single manager container, embedded sqlite (`arcane-data` volume; optional external
  Postgres); agent = one container per host. Lightest true multi-host option here.
  (https://getarcane.app/docs/get-started/installation.html)
- **Caveats**: much younger than Komodo (rewritten to v2 this year; churn is rapid — expect frequent
  upgrades and occasional breakage); smaller community; no equivalent of Komodo's TOML resource
  sync/procedures depth (has webhooks + updater + API instead).

## 3. Dockge (+ a TUI) — *lightweight compose-only option*

https://github.com/louislam/dockge · https://dockge.kuma.pet

- **What**: compose-stack-oriented UI from the uptime-kuma author. TypeScript, MIT, 24.6k★.
  File-based philosophy: stacks stay as plain `compose.yaml` under `STACKS_DIR` — no lock-in.
- **Multi-host**: yes, since 1.4.0 — but the "agent" is a **full second Dockge instance** per host;
  the primary proxies to it. Each stays independently usable.
  (https://github.com/louislam/dockge/releases/tag/1.4.0-beta.0)
- **Compose + git**: edit/deploy/inspect compose files on each host's stacks dir; **no git
  integration** — git sync stays your own `git pull`/`just` recipe per host.
- **Terminal**: none built in — pair with lazydocker/ssh.
- **Footprint**: one ~small container per host.
- **Caveats**: **release cadence is slow** — latest tag is 1.5.0 (2025-03-30), last code push
  2026-04-25; 173 open issues. No images/volumes/registries management, no RBAC to speak of, no
  update-check pipeline. It's deliberately minimal.

## 4. Dockman — *compose-file-first, agentless multi-host*

https://github.com/RA341/dockman · https://dockman.radn.dev

- **What**: "unfiltered access to your Docker Compose files" — web UI centered on editing
  compose files directly, keyboard-driven. TypeScript, AGPL-3.0, 648★, v3.2.0 (2026-02-13).
- **Multi-host**: connects to remote hosts over **SSH tunnels** — agentless, needs only ssh + docker
  group on the target. (https://dockman.radn.dev/docs/multihost/overview)
- **Terminal**: none.
- **Caveats**: single-author, young (June 2025); no git sync, no RBAC/audit, no builds. Nice UX but
  thin ecosystem vs Komodo/Arcane.

## 5. Sencho — *promising fleet model, pre-1.0*

https://github.com/Studio-Saelix/sencho

- Same-binary peer nodes joined by API tokens (primary proxies over HTTP/WS), plus a **Pilot Agent**
  that dials outbound over a single WebSocket for NAT'd hosts — same trick as Portainer Edge /
  Arcane Edge. Compose files stay on host disk as source of truth; LinuxServer.io/Portainer-style
  template store. AGPL-3.0, 472★, created Feb 2026, commits active but the README itself warns
  pre-1.0 churn. No CLI.

## 6. Dockpeek — *dashboard/update-checker complement*

https://github.com/dockpeek/dockpeek

- Lightweight multi-host **dashboard**: clickable links to each container's web UI (Traefik-label
  aware — fits `phantomlink`+traefik setup), port map, live logs, image-update detection.
  Multi-host via `DOCKER_HOST_N_URL` env vars pointing at socket proxies; their own README example
  uses a Tailscale IP. MIT, 2.1k★, active (last push Aug 2026). Not a manager — no compose editing,
  no deploy pipeline. Could complement either pick for the "open the web UI" workflow Portainer's
  port links gave.

## Smaller/new entries (evaluate later, not now)

- **Composr** (Vansmak/composr, 350★, MIT): multi-host via raw `tcp://:2375` sockets — unencrypted
  docker API unless you wrap it; feature-rich on paper, tiny community.
- **DockPit** (amslertec/dockpit, ~1★): Rust+SvelteKit, agent model, right idea, no traction yet.
- **NEXUS**: landing page only (alvarito1983.github.io/nexus-web), agent-based multi-host + MIT,
  unverifiable maturity.

## Terminal tools (pair with any pick)

| Tool | Multi-host | Notes |
|---|---|---|
| **lazydocker** | One daemon per session; works over `DOCKER_HOST=ssh://ghost` — known quirk: it ignores docker *contexts* properly (issue #644), so use the env var, or run it on-host via `ssh -t ghost lazydocker` | 53k★, MIT, v0.25.2 Apr 2026. Compose-aware, logs/stats/restart. Best TUI. |
| **oxker** | `--host` / `$DOCKER_HOST` per invocation | 1.9k★, MIT Rust TUI, active. Lighter than lazydocker. |
| **dry** | `DOCKER_HOST`-based; swarm-aware | 3.3k★, MIT, v0.13.0 Mar 2026 — revived after dormancy. |
| **ctop** | `DOCKER_HOST` | metrics-only `top`; effectively dormant (last push Jul 2024). |

## Not a fit

- **Yacht** (Yacht-sh/Yacht, 3.9k★): single-host, template "app store" model. Dormant ~2022–2025; a
  community revival (wickedyoda) started landing commits Sept 2026 but it's still
  Flask/Vue/single-host — doesn't solve multi-node.
- **Runtipi** (9.7k★, GPL-3.0) / **CasaOS** (37k★, Apache-2.0): single-host "homeserver OS" app
  stores — they *own* the app layout and would replace, not manage, the existing
  `compose/<host>/<stack>` structure. Wrong shape.
- **Cosmos** (azukaar/Cosmos-Server, 6.2k★): single-host security gateway (auth proxy, anti-DDOS) —
  adjacent problem, not a fleet manager.
- **Dokploy / Coolify**: PaaS-shaped (own git→deploy pipeline, own domain model); don't adopt
  existing compose dirs as source of truth. Different product category.

## What would be lost vs Portainer

With **Komodo**: effectively nothing used here — multi-env + edge-style agents, git-deploy stacks +
webhooks, RBAC/OIDC, exec/logs in UI, audit trail all covered, and it *adds* builds, procedures,
and TOML resource sync. Only real loss: Portainer's app-template gallery (Komodo has none;
Arcane does have template registries) and k8s endpoint management (unused).

With **Arcane**: same coverage minus Komodo's build-fleet/procedures depth; gains vuln scanning and
S3 backups Portainer CE lacks.

With **Dockge/Dockman/Sencho** alone: lose env-level RBAC, image/registry management, update
detection, and any automation hooks.

## Recommendation

**Komodo** on ghost as `compose/ghost/komodo/` (traefik → `komodo.paynepride.com`):

- Core + MongoDB (or FerretDB) on ghost; periphery systemd agent on ghost, babyblue, ghost-vault,
  aurora — all outbound to Core, so tailnet-only, no inbound ports.
- Import ghost's ~40 running projects by compose project name → zero-downtime adoption.
- Then optionally move stacks to **git-repo mode** against this monorepo (clone on host + Forgejo
  push webhook → auto-redeploy) — upgrades today's `docker --context ghost compose up -d` into real
  GitOps without changing the repo layout.
- `km` binary covers the terminal half (`km deploy`, `km ssh`, `km exec`) + lazydocker for
  interactive browsing.

**Choose Arcane instead** if the MongoDB dependency / extra infra is the dealbreaker — it gives ~90%
of the day-to-day surface in a single sqlite-backed container and is the fastest-moving project in
the space. Watch it either way; it's viable today and improving weekly.

Keep **Dockpeek** (optional) for the cross-host "open web UI" dashboard and **lazydocker/oxker** as
the interactive TUI regardless of control-plane pick.

Next step if approved: `compose/ghost/komodo/` stack + periphery install notes, run alongside
Portainer, then cut DNS over and retire `portainer`/`portainer-agent` stacks.

## Sources

- Komodo: https://github.com/moghtech/komodo · https://komo.do/docs/intro ·
  https://komo.do/docs/setup · https://komo.do/docs/setup/connect-servers ·
  https://komo.do/docs/deploy/compose · https://komo.do/docs/ecosystem/cli ·
  https://github.com/moghtech/komodo/releases/tag/v2.3.3
- Arcane: https://github.com/getarcaneapp/arcane · https://getarcane.app/docs ·
  https://getarcane.app/docs/remote/environments.html ·
  https://getarcane.app/docs/docker/git-sync.html ·
  https://getarcane.app/docs/reference/cli/commands.html ·
  https://getarcane.app/docs/get-started/installation.html ·
  https://github.com/getarcaneapp/arcane/releases/tag/v2.15.1
- Dockge: https://github.com/louislam/dockge ·
  https://github.com/louislam/dockge/releases/tag/1.4.0-beta.0 (multi-agent) ·
  https://github.com/louislam/dockge/releases/tag/1.5.0 (latest)
- Dockman: https://github.com/RA341/dockman · https://dockman.radn.dev/docs/multihost/overview
- Sencho: https://github.com/Studio-Saelix/sencho
- Dockpeek: https://github.com/dockpeek/dockpeek (README multi-host env vars)
- Composr: https://github.com/Vansmak/composr · DockPit: https://github.com/amslertec/dockpit ·
  NEXUS: https://alvarito1983.github.io/nexus-web/
- lazydocker: https://github.com/jesseduffield/lazydocker ·
  https://github.com/jesseduffield/lazydocker/issues/644 (ssh context caveat) ·
  https://qmacro.org/blog/posts/2024/08/24/using-lazydocker-with-ssh-based-remote-contexts/
- oxker: https://github.com/mrjackwills/oxker (README `--host`)
- dry: https://github.com/moncho/dry · ctop: https://github.com/bcicen/ctop
- Yacht: https://github.com/Yacht-sh/Yacht (revival commits Sept 2026) ·
  Runtipi: https://github.com/runtipi/runtipi · CasaOS: https://github.com/IceWhaleTech/CasaOS ·
  Cosmos: https://github.com/azukaar/Cosmos-Server
- Current Portainer stacks: `compose/ghost/portainer/docker-compose.yml`,
  `compose/babyblue/portainer-agent/`

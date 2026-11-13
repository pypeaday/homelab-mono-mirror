# Observability + Alerting Plan

> Status: Approved — SigNoz chosen
> Created: 2026-10-04

## Goal

Spans/traces for every app and container, notifications on failures, backup-restore tests in CI.

## Reality check

Most homelab services are third-party images that will never emit OTel traces.
Coverage comes in layers:

| Layer | Coverage | How |
|---|---|---|
| Ingress | Every HTTP request to every web app (45+ services) | **Traefik v3 OTLP tracing** — one flag, spans for entrypoint→router→service per request |
| App internals | Custom apps only (homelab-stack, pype.dev, etc.) | OTel SDK / `opentelemetry-instrument` per app |
| Metrics | All containers + hosts | OTel collector `docker_stats` + `hostmetrics` receivers; `/metrics` where apps expose it (immich, forgejo, traefik, postgres exporters) |
| Logs | All container stdout/stderr | OTel `filelog` receiver on `/var/lib/docker/containers` |
| Uptime | All web services | uptime-kuma (or SigNoz/Grafana synthetics) |

## Architecture

```
apps ──OTLP──► otel-collector ──► backend (SigNoz or Tempo/Loki/Prom)
traefik ─OTLP─┘        ▲               │
docker stats ──────────┘               ▼
host metrics ──────────┘         alerts ──► gotify/apprise ──► phone
container logs ────────┘
```

- New stack: `compose/ghost/observability/` (+ agent collector on babyblue later — it's offline)
- Everything through Traefik as usual: `signoz.paynepride.com` or `grafana.paynepride.com`

## Decision: backend — **SigNoz** (decided 2026-10-04)

Starting point: official deploy at `third-party/signoz` clone in the July backup
(`deploy/docker/clickhouse-setup/`), or fresh copy from upstream.

**Option A — SigNoz** (recommended for this goal)
- One compose stack: ClickHouse + OTel collector + query-service + UI
- Best trace UX out of the box (flamegraphs, service map, trace→logs)
- Built-in alerting → webhook → gotify
- Heavier: ClickHouse, ~2-4G RAM steady-state
- Resurrect the `signoz` repo from the July backup for a starting compose

**Option B — Grafana LGTM** (Prometheus + Loki + Tempo + Grafana + Alertmanager)
- Standard, modular, Grafana dashboards
- ~6 services to wire together; more YAML, more flexibility
- Alertmanager → gotify via webhook

## Rollout

1. ~~**Traefik v2.4 → v3**~~ — was already done (v3.6.12 live); PLAN.md was stale
2. ~~Deploy backend + collector; verify a trace from any traefik-routed app~~ — **DONE 2026-10-05**: SigNoz live at signoz.paynepride.com; traefik OTLP → `localhost:4317` (traefik is host-networked, not on phantomlink); docker_stats + hostmetrics + logspout logs all ingesting
3. ~~Enable `docker_stats` + log receivers~~ — DONE (docker_stats needed `api_version: "1.40"` for ghost's daemon floor)
4. Instrument homelab-stack apps (FastAPI → `opentelemetry-instrumentation-fastapi` in the image or env-var agent)
5. uptime-kuma stack for HTTP checks on all public services
6. Alerts → gotify: service down, 5xx rate, container restart loops, disk/mem pressure, backup failures; zpool status → alert on DEGRADED (harbor is degraded NOW)

## Backup-test CI (folds into this)

Forgejo Actions (runner already runs on ghost), scheduled workflow:
- `restic check` on `sftp:nic@ghost:/tank/encrypted/nas/nic-home/`
- `restic restore latest --target /tmp/restore-test` + file-count assertion
- POST result to gotify → notification on pass/fail
- Later: same pattern for a docker-volume restore test (zfs clone + mount + sanity check)

## What we already have (don't rebuild)

- gotify ✓ deployed — notification target
- apprise ✓ deployed — notification router if needed
- netdata + glances ✓ host dashboards — keep or consolidate to beszel
- beszel ✓ installed but unused — lightweight host metrics, cheap win to enable
- forgejo-runner ✓ — CI executes on ghost already

## Querying (agent access)

- **CLI**: `scripts/signoz-sql "SELECT ..."` — SQL over ClickHouse on ghost.
  Tables: `signoz_traces.distributed_signoz_index_v3`, `signoz_logs.*`, `signoz_metrics.*`
- **API**: `http://ghost:3301` (SigNoz UI/query-service, `SIGNOZ-API-KEY` PAT header)
- **Ingest**: OTLP `signoz-otel-collector:4317` (gRPC) / `:4318` (HTTP) on `phantomlink`
- **First instrumented app**: notifiq (FastAPI + Temporal worker traces, logs via OTLP) — 2026-10-05

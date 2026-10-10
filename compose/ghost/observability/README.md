# observability — SigNoz on ghost

Traces, metrics, logs for the whole lab. See `plans/observability.md` for the design.

## What's in here

- **SigNoz**: clickhouse + zookeeper + query-service + frontend + alertmanager
- **signoz-otel-collector**: OTLP receivers (4317 grpc / 4318 http, also reachable on
  `phantomlink` as `signoz-otel-collector`), hostmetrics (via `/hostfs`),
  docker_stats (per-container cpu/mem/net/io via docker.sock),
  container logs via logspout → tcplog :2255
- Data lives at `/tank/encrypted/docker/signoz-zfs/`

## First-time setup

```bash
ssh ghost
sudo rm -rf /tank/encrypted/docker/signoz-zfs   # docker auto-created a plain dir
sudo zfs create tank/encrypted/docker/signoz-zfs
sudo chown nic:nic /tank/encrypted/docker/signoz-zfs
sudo chmod 2775 /tank/encrypted/docker/signoz-zfs
```

Then register for snapshots in `/etc/sanoid/sanoid.conf` (per-dataset blocks, `recursive = no`
— no block means no snapshots and no harbor replication):

```
[tank/encrypted/docker/signoz-zfs]
  use_template = docker
  recursive = no
```

`sudo systemctl reload-or-restart sanoid`, and mirror the block into
`zfs-ops/hosts/ghost/sanoid.conf`.

## Deploy

```bash
cd compose/ghost/observability
cp .env.example .env
just deploy   # or: docker compose up -d
```

UI: https://signoz.paynepride.com (traefik, whitelisted)

## Gotcha: logspout needs `TAIL=0`

logspout's default `TAIL=all` makes dockerd scan every container's whole
json log on each (re)attach to find "lines since now". With unrotated logs
(jellystat hit 163 GB) that pinned dockerd at ~1000% CPU / ~480 MB/s reads.
Keep `TAIL=0`. Logspout also stamps lines with send time, so it can't
backfill history with real timestamps.

## Sending traces in

- Traefik v3 (planned upgrade): OTLP gRPC → `signoz-otel-collector:4317`
  (`--tracing.otlp.grpc.endpoint=signoz-otel-collector:4317` + insecure)
- Apps on phantomlink: same endpoint
- Off-network senders on tailscale: `ghost:4317` (TLs port binds)
- **Cloudflare Workers / public senders**: OTLP HTTP via
  `https://otel.paynepride.com${OTEL_INGEST_PATH}v1/{logs,traces}` —
  a Traefik route on the collector strips `OTEL_INGEST_PATH` (a capability
  path; self-hosted SigNoz has no ingest auth). See
  `terraform-cloudflare-factory/OBSERVABILITY.md`.

## Alerts

Alertmanager is wired into query-service. Route notifications to gotify
(gotify.paynepride.com) via SigNoz UI → Alert Channels → webhook.

## Next steps tracked in plans/observability.md

- uptime-kuma stack for HTTP checks
- homelab-stack FastAPI instrumentation
- backup-restore Forgejo Actions workflow

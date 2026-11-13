# j-sentinel observability

Not a compose stack — j-sentinel is a Windows 11 laptop with no docker.
`otelcol-contrib` runs as a native Windows service (`otelcol-contrib`,
installed by MSI, auto-start) and ships OTLP → `100.64.184.5:4317`
(SigNoz on ghost), tagged `host.name=j-sentinel`.

- `otelcol-contrib-config.yaml` — hostmetrics + Windows Event Log
  (Application/System) receivers; file-backed send queue at
  `C:\ProgramData\otelcol-contrib\queue` survives sleep/WAN drops.
- `install.ps1` — idempotent installer (MSI + config + service). Pinned to
  otelcol-contrib 0.164.0.
- `deploy.sh` — run from aurora: pushes both files over ssh and runs the
  installer remotely. Re-run it after editing the config.

Remote shell is PowerShell — keep ssh remote args single-quoted, no nested
quotes, or pipe commands via `ssh minec@j-sentinel powershell` on stdin.

Also on the box: scheduled task `SentinelWatch-Clips` (every 30 min, runs
`Watch-Clips.ps1`) writes Application event `SentinelWatch`/4711 when the
newest Reolink clip is >24h old; the eventlog receiver ships it to SigNoz.

SigNoz rules (all → Alert Triage, warning):

- **26** `j-sentinel silent - no telemetry` — `count_over_time(
  system_cpu_time{host_name="j-sentinel"}[15m])` = 0 (~15 min of silence:
  laptop asleep/off, tailscale or remote WAN down).
- **27** `j-sentinel disk nearly full` — `system_filesystem_usage
  {state="free"}` < 15 GB on any mount (clip store filling while
  ghost can't pull = footage loss risk).
- **28** `sentinel-vid sync failing` — ≥3 `CRITICAL` log lines from the
  `sentinel-vid-sync` container in 30 min (ssh/tailnet pull failures).
- **29** `Reolink clips stale on j-sentinel` — any `SentinelWatch` event
  in 60 min (hub not writing clips for 24h+).

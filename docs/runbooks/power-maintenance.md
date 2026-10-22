# Power & Maintenance Runbook

How to shut down, physically move, and power back up the homelab with
confidence. Audited 2026-10-19 against live state on ghost, ghost-vault,
aurora, and the router.

## Topology at a glance

| Box | Role | Storage | Boot risks |
| --- | --- | --- | --- |
| **OPNsense** @ 192.168.1.1:8443 | router, DHCP, gateway | own appliance | none — designed for reboots; config backup is the gap (see below) |
| **pihole3** @ 192.168.1.4 | LAN DNS only (no DHCP) | own box | none; boots independently. While it's off, LAN has no DNS |
| **ghost** @ 192.168.1.9 | docker host (~126 containers, ~57 compose projects), libvirt (homeassistant VM), SigNoz, traefik, Forgejo, Komodo core, Gotify | nvme root + ZFS pools `tank` (primary, encrypted, 87% full), `harbor` (local mirror replica, encrypted), `frigate-media` | ZFS key-load → mount → docker ordering is unguarded (below) |
| **ghost-vault** | offsite-style ZFS replica of ghost + observability forwarders | `tank` 3.6T | docker.socket-enabled — comes back fine |
| **aurora** | desktop, distrobox dev, ollama/stable-diffusion, MCP containers, restic client | ext4/ZFS mix | linger on, docker.socket enabled — comes back; leaked MCP containers are cosmetic |

### Data flow (backups)

```text
tank/encrypted (ghost, live)
  ├─ sanoid snapshots (local, ~15min/daily/weekly per template)
  ├─ syncoid → harbor/encrypted (ghost, same chassis) hourly — ALL children
  ├─ syncoid → ghost-vault:tank/encrypted hourly — SUBSET (see gaps)
  └─ restic daily: aurora /home/nic → sftp:ghost:/tank/encrypted/nas/nic-home
       (covers all working repos, .env files, dotfiles — then replicated
        onward by the zfs copies above)
```

Replication health pings healthchecks.io per-leg; failures also push Gotify.

## What happens on a power cut + power restore

### Comes back automatically (verified live)

- ghost: ssh.socket ✓, tailscaled ✓, docker (+socket) ✓, libvirtd ✓,
  115 `unless-stopped` + 11 `always` containers ✓, ZFS file-keyed datasets
  mount via `zfs-load-key.service` (key at `/home/nic/.zfs.tank.key`)
- homeassistant VM — **autostart now enabled** (was disabled; fixed today)
- ghost-vault: tailscaled ✓, docker.socket ✓, collectors restart
- aurora: linger ✓, tailscaled ✓, docker.socket ✓, user units (collie,
  devin-dream, nas-backup timer) survive without login
- OPNsense + pihole: independent appliances, self-boot
- Komodo periphery/core are containers — they return with docker

### Does NOT come back / needs attention

1. **`zfs-load-key.service` fails every boot** — `zfs load-key -ra` tries the
   `keylocation=prompt` children of `harbor/encrypted` (~12 stale datasets,
   all unmounted leftovers from the tank migration) and fails non-interactively.
   File-keyed datasets still load, so it's noisy-not-fatal **today** — but it
   means a real key failure would also be ignored, and nothing alerts.
2. **docker↔ZFS ordering gate exists but is toothless.** Ghost has
   `docker-wait-for-zfs.service` (`Before=docker.service`, `After=zfs.target`)
   and critical-chain confirms docker waits for `zfs.target` at boot. Two
   defects remain: (a) `ExecStart=/bin/true` — it never verifies keys loaded
   or datasets mounted, so a key failure still means docker starts against
   empty bind-mount dirs (this already happened once — the root-owned
   skeleton at `~/projects/personal/homelab-mono` on ghost); (b) the unit has
   `RequiredBy=docker.service` in `[Unit]`, which systemd **ignores**
   (journal: "Unknown key name") — the gate only engages because it's
   `WantedBy=multi-user.target`; a manual `systemctl start docker` bypasses
   it. Fix below.
3. **`meme-search-pro`** — a stray `docker run` Rails container (not in any
   compose file). restart policy now set; decide if it's keeping.
4. **`forjeo-db-1`** — orphan postgres from a typo'd duplicate of forgejo
   (`/var/home/...`, `restart=always`). Verify it's unused, remove.
5. **No deadman's switch for ghost itself.** Gotify, SigNoz, traefik all live
   ON ghost — during a ghost outage nothing can notify you. hc-ping covers
   replication legs only. Add a "ghost-alive" check (below).
6. **Vault replication coverage — fixed 2026-10-19.** ghost-vault now
   receives every docker/* control dataset (forjeo, komodo, karakeep,
   repoflow, temporal, signoz — the earlier gap) plus `nas/games` and
   `nas/nic-home` (the restic repo, ~774G). Deliberately excluded (vault is
   3.6TiB, keep <75%): `nas/media` (7.2T replaceable bulk), `tdarr_cache`,
   dormant VM disks (ubuntu22-sandbox, win10, talos01, digital-harbor,
   block-subnet-router, try-cockpit). Exclusions are documented at the top
   of `zfs-ops/hosts/ghost-vault/syncoid-replication.sh`.
7. **`harbor` pool has 1 permanent data error** (post-resilver; the spare
   drive was consumed — cron already reminds you Oct 10 to buy one).
   `sudo zpool status -v harbor` to see the file. It's a replica copy — low
   urgency, but it is not self-healing.
8. **No ZFS scrub timers enabled** — `zfs-scrub-monthly@.timer` etc. are
   disabled; last scrubs were manual (Oct 11–12). Enable monthly scrubs.
9. **`systemd-networkd-wait-online` failed** — networking-online ordering is
   unreliable on ghost; mostly cosmetic but don't depend on it.
10. **Secrets**: stack `.env` files are gitignored. Ghost-side `.env`s live
    inside their `*-zfs` datasets (covered by harbor; only partially by
    vault). Aurora-side `.env`s are in `/home/nic` → restic daily. No
    additional action needed once vault coverage is extended.
11. **OPNsense config backup** — export or API-backup the config to the
    restic path; the router reboots fine, but its config is the thing you'd
    miss if the box died.
12. **BIOS power-on-AC-loss** — verify on next physical visit for ghost,
    ghost-vault, router, pihole. Can't check remotely; essential for
    unattended power cuts.
13. **Docker on aurora starts via socket activation** (`docker.service`
    disabled, `docker.socket` enabled). Works today; one odd boot could
    leave containers down until something pokes the API. `sudo systemctl
    enable --now docker.service` removes the fragility.
14. **Stale cruft**: `babyblue`/`babyblue-aurora` tailnet entries (offline),
    ~60 leaked MCP containers on aurora, dead compose projects (minecraft,
    cannalyze, test-nginx, cloudflared-santa). Cosmetic; clean when bored.
15. **tank at 87%** — ZFS degrades past ~90%; plan a cleanup pass
    (`nas/dump`, `games`, `torrents` are the likely bulk).

## Shutdown order

Physical move or full power cut:

```text
1. pihole        — nothing depends on it mid-move; shutdown whenever
2. ghost         — virsh shutdown homeassistant (ACPI; give it ~60s)
                   optional grace: docker stop $(docker ps -q) — or just
                   let systemd do it; then shutdown -h now
3. ghost-vault   — shutdown -h now (mid-replication is safe; syncoid resumes)
4. aurora        — normal desktop shutdown
5. OPNsense      — shutdown from UI or power button; goes last so you keep
                   DHCP/DNS/gateway while the rest go down
```

## Startup order

```text
1. OPNsense   — wait for web UI + WAN up
2. pihole     — DNS back for the LAN
3. ghost      — boots itself: zfs import → load-key → mount → docker
4. ghost-vault
5. aurora
```

Then run the verification script (below) — do NOT eyeball it.

## Verification

```bash
scripts/maintenance/ghost-preflight.sh
```

Checks: pool health, key status, mounts, enabled boot units, container
restart policies, VM autostart, replication freshness, failed units, disk
headroom — on ghost and ghost-vault. Run it **before** shutdown (baseline)
and **after** power-on; diff the output. Green = walk away.

## Fixes to apply (need sudo on ghost / accounts)

```bash
# Fixes 1–4 (docker-wait-for-zfs hardening, monthly scrubs, harbor -v
# error list, aurora docker.service) are wrapped in a wizard that applies
# them over ssh with one sudo prompt and re-runs the preflight after:
scripts/maintenance/harden-ghost-boot.sh

# 5. External deadman: create an hc-ping check "ghost-alive" (5 min),
#    then on ghost add to crontab:
#    */5 * * * * curl -fsm5 https://hc-ping.com/<uuid>/ghost-alive
#    healthchecks alerts you when it goes quiet — works even when
#    gotify/signoz are down with ghost.

# 6. OPNsense config backup: UI → System → Configuration → Backups →
#    download; or API GET /api/core/backup/download. Drop the file in
#    ~/backups/opnsense (restic picks it up nightly).

# 7. Vault coverage — DONE (2026-10-19, zfs-ops d70ae53). First sends run
#    on the hourly timer; ~855G initial transfer, a few hours over LAN.
#    Verify later: ssh ghost-vault 'zfs list -r tank/encrypted/docker'
```

## Incident log

### 2026-10-21 — ZFS kernel panic + hard reboot

**Symptom:** All I/O on `tank` froze mid-afternoon. Load hit ~650; ~15
processes (postgres, apache, minio, both zfs sends) stuck in D state;
pool reported 0 IOPS while disks sat idle with zero hardware errors.

**Cause:** Kernel logged `PANIC: tank: blkptr ... has invalid TYPE 62` —
a write thread hit a corrupted block pointer and wedged inside
`zfs_panic_recover`. Hardware was clean; this was metadata corruption
already present on the pool (tank had flagged data errors before the
crash). Concurrent sanoid + harbor-sync + vault-pull traffic was the
likely trigger that walked into it, not the cause.

**Recovery:** `sudo reboot`. Shutdown stalled on the frozen pool; box
needed a hard power cut. Pool imported cleanly on boot (no panic
replay). `signoz-clickhouse` crash-looped post-boot: 106 empty broken
parts on `signoz_metrics.time_series_v4_6hrs` exceeded the
`max_suspicious_broken_parts` limit (default ~100) so the table refused
to attach. Fix: temporarily raise the limit in
`signoz-zfs/config/clickhouse-config.xml` (`<merge_tree>` block is
already there, commented), `docker restart`, confirm healthy, revert
the config. No sudo needed — that config dir is nic-owned.

**Outcome:** Full recovery. Preflight 32 PASS / 3 known WARN / 0 FAIL.
Bonus: sanoid's aggressive `media` template pruned ~3.2T of
snapshot-pinned data post-reboot — tank dropped from 87% to 60%.

**Still open:**
- `tank` has 2 data errors, `harbor` 1 — files unidentified until
  `sudo zpool status -v <pool>` (root-only output; wizard covers it)
- The corrupt metadata still exists — a future write hitting the same
  path **can panic again**. Priority: identify the objects, run a scrub,
  restore the damaged files from harbor/vault replicas if real data.
- Consider pausing `harbor-replication.timer` until `status -v` is read
  if you want zero risk of re-triggering before the damage is known.

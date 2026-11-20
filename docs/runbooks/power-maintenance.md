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
# Fixes 1–3 DONE 2026-10-27 (harden-ghost-boot.sh): docker-wait-for-zfs
# hardened (mountpoint checks + RequiredBy), monthly scrubs on for all
# pools, zpool status -v run on both pools. Re-run the wizard only if
# the unit regresses. Still open: aurora docker.service (stage 4).
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

**Follow-up (2026-10-27):**
- `harden-ghost-boot.sh` wizard ran clean: `docker-wait-for-zfs` now does
  real mountpoint checks with `RequiredBy=docker.service` in `[Install]`;
  monthly scrub timers enabled for all three pools; aurora docker.service
  stage skipped/pending.
- Errors decayed: harbor `1 → 0` (bad snapshot aged out), tank `2 → 1`.
- Learned: `tank` is a 2-disk mirror (ST12000VN0008 + ST12000NM0127), so
  scrubs can repair bad blocks from the good leg — not just detect them.
- **Still open:** tank's 1 remaining error — name the object with
  `sudo zpool status -v tank` (root-only). If it's a real file, restore
  it from a harbor/vault replica; if it's in an old snapshot it will
  self-clear on the next prune.

### 2026-11-03 — ghost-vault pool filled by unpruned replica snapshots

**Symptom:** `ghost-vault-docker` healthcheck silent ~10h;
`syncoid-replication.service` failing hourly with
`cannot receive incremental stream: out of space`. Pool at 96%.

**Cause:** Vault runs sanoid in prune-only mode (`autosnap=no`) keyed to
`hosts/ghost-vault/sanoid.conf`, but the config was never updated when
new datasets joined replication (10-20). forjeo/signoz/nic-home/etc.
accumulated ~6k snapshots that ghost had already pruned.

**Fix:** deleted 5,634 vault-only snapshots (snaps absent on ghost can
never be incremental bases), then added all replicated datasets to
vault's `sanoid.conf` (docker template for `docker/*`, production for
`nas/*`). Deploys via symlink `/etc/sanoid/sanoid.conf → ~/zfs-ops/...`
on vault — git pull is the deploy.

**Rule going forward:** any dataset added to a `syncoid-replication.sh`
must also be added to that host's `sanoid.conf` — replication without
prune coverage is a pool-filler. Same applies to harbor's
`sync-harbor.sh` + ghost's `sanoid.conf` (already covered, verified).

**Second bug same day:** a transient hc-ping.com outage killed a run —
curl failures propagated under `set -e`. All pings now `|| true`
(zfs-ops `ccac1fd`). Monitoring outages can no longer block replication.

**Scrub result:** tank's Nov 1 scrub completed 0 errors — the post-panic
corruption is fully resolved; all three pools report no known errors.

### 2026-11-03 — SigNoz alert revision + vault metrics coverage

**New alert rules** (all hosts): D-state pileup (`node_procs_blocked>25`),
load critical (`node_load15>30`), sanoid health monitor, sanoid
snapshots monitor (CRIT only). The D-state rule is the direct signature
of the Oct-21 kernel wedge — would have paged in minutes.

**Vault metrics now flow** (were ghost-only):
- `sanoid_monitor_status{check=health|capacity|snapshots}` — pool
  capacity alerts now cover vault (its `/tank` fs metric is misleading;
  the 96% event was invisible to "Pool/disk nearly full")
- `zfs_pool_errors{pool=tank}` per-pool counters
- `syncoid_last_success_epoch{target=ghost-vault}` — vault puller now
  covered by "Replication stale"

**Plumbing:** `zfs-metrics.sh` (zfs-ops) writes textfiles; runs via cron
`*/10` with `TEXTFILE_DIR=/home/nic/textfiles` +
`SANOID_CACHE_DIR=/home/nic/.sanoid-cache` (unprivileged sanoid needs
the cache-dir override). Vault's signoz-node-exporter was recreated with
`--collector.textfile.directory=/textfiles` + bind mount.
**⚠ The compose edit on vault's homelab-monitoring clone is uncommitted**
— commit it or a checkout kills the textfile mount.

**sanoid.conf (vault):** all replicated datasets must appear (docker
template for docker/*, production for nas/*). `vms/pihole` has
`monitor = no` (frozen archive — send disabled, no source snaps).
New datasets too young for monthlies get `monitor_dont_crit = yes`.

**Still uncovered:** docker container health (no cadvisor metrics —
signoz-clickhouse's crash-loop was invisible) and the ghost-down blind
spot itself — SigNoz lives on ghost, so the hc-ping `ghost-alive`
deadman remains the only way to catch a total ghost outage.

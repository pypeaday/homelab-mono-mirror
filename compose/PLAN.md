# Homelab Modernization Plan

> Status: In Progress
> Last Updated: 2026-03-23

## Overview

This document tracks the work to modernize the homelab infrastructure with the following goals:
1. ~~Add Cloudflare Tunnel for external access~~ **PAUSED** - Deferring for now
2. **Upgrade Traefik** to modern version
3. Add Tailscale for cross-host container networking
4. Establish consistent deployment patterns using `just` recipes
5. Clean up compose stacks for maintainability
6. Set up Renovate for automated image updates

### Current Priorities

1. **Traefik Upgrade** - v2.4 is EOL, upgrade to latest v3
2. **Compose Stack Cleanup** - Standardize patterns, improve maintainability
3. **Just Recipes** - Consistent deployment commands
4. **Renovate** - Automated updates

### Architecture (Current)

```
Internet → Cloudflare → Traefik → Containers (via 80/443)
                                   ↑
                         ghost & babyblue via Tailscale
```

### Architecture (Deferred - Cloudflare Tunnel)

```
Internet → Cloudflare Edge → cloudflared → Traefik → Containers
                                              ↑
                                    ghost & babyblue via Tailscale
```

---

## Current State

### Hosts
- **ghost**: Primary host, runs most services
- **babyblue**: Secondary host, GPU-heavy services (AI, media processing)

### Service Count
- ~35 active services on ghost
- ~10 services on babyblue
- 2 deprecated services (archived: nitter, bentopdf)
- 3 unused services (beszel, apprise, duplicati)

### Key Constraints
- Need cross-host networking: ghost containers must call babyblue containers (e.g., ollama)
- Docker Compose doesn't natively solve multi-node networking
- Want to close ports 80/443 on firewall
- Traefik v2.4 is currently used (EOL, but still functional)

---

## Decisions Made

| Decision | Choice |
|----------|--------|
| Deprecated services | Move to `compose/archived/` |
| Repoflow secrets | Move to `.env` first |
| External access | Direct 80/443 (Cloudflare Tunnel PAUSED) |
| Cross-host networking | Tailscale for ghost ↔ babyblue container communication |
| Traefik upgrade | Upgrade to v3 (latest stable) |
| Compose cleanup | Standardize patterns across all stacks |
| Renovate timing | Add after traefik upgrade |
| Service grouping | Structure-agnostic (just recipes handle deployment) |

---

## Service Inventory

See: `compose/services.csv`

### Ghost Active Services (~35)

| Service | Domain | Notes |
|---------|--------|-------|
| actual | actual.paynepride.com | Budget app |
| affine | affine.paynepride.com | Multi-service (postgres, redis) |
| apprise | - | Not currently used |
| archivebox | archivebox.paynepride.com | Multi-service |
| arrs | various | 13 services: readarr, audioreadarr, lidarr, radarr, sonarr, bazarr, ombi, jellyseerr, prowlarr, gluetun, transmission, tdarr |
| beszel | - | Not currently used |
| chatgpt-telegram-bot | - | Not currently used |
| code-server | code.paynepride.com | |
| container-registry | registry.paynepride.com | Multi-service (registry + ui) |
| dashy | - | Config-only service |
| domain-locker | domain-locker.paynepride.com | Multi-service |
| duplicati | - | Not currently used |
| eigenfocus | eigenfocus.paynepride.com | |
| forgejo | git.paynepride.com | Multi-service (dind, runner) |
| freshrss | freshrss.paynepride.com | |
| frigate | frigate.paynepride.com | |
| gotify | gotify.paynepride.com | |
| grist | grist.paynepride.com | |
| homelab-stack | various | 7 custom apps: audiomass, gh-star-sorter, dad-can-i-wear-this, whose-turn-is-it, gwl-marg-tracker, santa-tracker, clocks |
| homebox | homebox.paynepride.com | |
| images.pype.dev | shotput.paynepride.com | |
| immich | immich.paynepride.com | Multi-service |
| immich-memes | - | Separate immich for meme photos |
| installer | i.paynepride.com | Custom app |
| kanboard | kanboard.paynepride.com | |
| karakeep | karakeep.paynepride.com | Multi-service |
| linkding | linkding.paynepride.com | |
| manyfold | manyfold.paynepride.com | Multi-service |
| media-stack | various | jellyfin, jellystat, audiobookshelf, ubooquity, pinchflat |
| meme-search | meme-search.paynepride.com | Multi-service |
| minio | s3.paynepride.com, minio.paynepride.com | |
| monitoring-visibility | glances.paynepride.com, netdata.paynepride.com | Needs attention post-consolidation |
| nextcloud | nextcloud.paynepride.com | Multi-service |
| nostr-relay | n.paynepride.com | |
| paperless-ngx | paperless.paynepride.com | Multi-service |
| portainer | portainer.paynepride.com | |
| postiz | postiz.paynepride.com | Multi-service |
| re-director | redirector.paynepride.com | |
| searxng | searxng.paynepride.com | Multi-service |
| stirlingtools | stirlingtools.paynepride.com | |
| syncthing | - | LAN-only |
| temporalio | temporal.paynepride.com, temporal-ui.paynepride.com | Multi-service |

### Babyblue Active Services (~10)

| Service | Domain | Notes |
|---------|--------|-------|
| ai | - | ollama, open-webui, whisper, speakr |
| beszel-agent | - | |
| code-server | - | |
| developer-stack | - | mcphub, qdrant |
| immich-remote-ml | - | |
| khoj | - | Multi-service |
| kotaemon | - | |
| monitoring-visibility | - | Needs attention post-consolidation |
| portainer-agent | - | |
| tdarr | - | Transcoding node |
| timetracker | - | Multi-service |

---

## Execution Phases

### Phase 0: Prep

- [x] **CP0-A**: Archive deprecated services (nitter, bentopdf → `compose/archived/`)
- [x] **CP0-B**: Repoflow secrets to `.env`
- [x] **CP0-C**: Generate `compose/services.csv`

### Phase 1: Tailscale (Cross-Host Networking)

- [x] **CP1-T1**: Install/configure Tailscale on ghost
- [x] **CP1-T2**: Install/configure Tailscale on babyblue  
- [x] **CP1-T3**: Verify cross-host container communication

### Phase 2: Traefik Upgrade (PRIORITY)

- [x] **CP2-T1**: Research Traefik v3 migration path
- [x] **CP2-T2**: Update traefik docker-compose to v3
- [x] **CP2-T3**: Migrate config.toml syntax if needed
- [x] **CP2-T4**: Migrate config.yml to new format
- [x] **CP2-T5**: Test all routes and middlewares
- [ ] **CP2-T6**: Update traefik justfile recipe

### Phase 3: Compose Stack Cleanup

- [x] **CP3-C1**: Audit all compose files for consistency
- [x] **CP3-C2**: Fix label quoting (traefik.enable: "true")
- [x] **CP3-C3**: Network rearchitecture (no changes needed)
- [x] **CP3-C4**: Common patterns documented in compose/README.md
- [ ] **CP3-C5**: Document common patterns

### Phase 4: Just Recipes

- [ ] **CP4-A**: Create `compose/justfile`
- [x] **CP4-B**: Create `infrastructure/justfile`

### Phase 5: Renovate

- [ ] **CP5-A**: Add `renovate.json`

### Phase 6: Cloudflare Tunnel (Future)

- [ ] Revisit when traefik upgrade is stable

### Phase 7: pype.dev (Future)

- [ ] Migrate from Cloudflare Pages to self-hosted

---

## Detailed Checkpoints

### CP0-A: Archive Deprecated Services

**Summary:** Move deprecated services to a dedicated folder rather than deleting, preserving configuration for future reference.

**Services archived:**
- `compose/ghost/nitter` → `compose/archived/nitter`
- `compose/ghost/bentopdf` → `compose/archived/bentopdf`

**Commands:**
```bash
mkdir -p compose/archived
mv compose/ghost/nitter compose/archived/
mv compose/ghost/bentopdf compose/archived/
git add compose/archived/
git commit -m "chore: archive deprecated services (nitter, bentopdf)"
```

**Status:** ✅ Complete (User executed)

---

### CP0-B: Repoflow Secrets to .env

**Summary:** Move hardcoded secrets from compose file to `.env` for proper secret management.

**Secrets to extract:**
- `GENERAL_COOKIE_SECRET`
- `S3_ACCESS_KEY` / `S3_SECRET_KEY`
- `HASURA_ADMIN_SECRET`
- `JWT_SECRET`
- `RESET_PASSWORD_JWT_SECRET`
- `PERSONAL_ACCESS_TOKEN_JWT_SECRET`
- `DEFAULT_ADMIN_PASSWORD`
- `POSTGRES_PASSWORD` (for postgresql service)
- `MINIO_ROOT_PASSWORD`

**Actions:**
1. Create `compose/ghost/repoflow/.env` with all secrets
2. Update compose to reference `${VAR_NAME}` instead of raw values
3. Verify `.env` is in `.gitignore`
4. Test that repoflow still starts correctly

**Status:** ✅ Complete

---

### CP0-C: Generate Service Inventory CSV

**Summary:** Create a complete, verified list of all active services as source of truth.

**Output:** `compose/services.csv`

**Fields:**
- service, host, port, internal_port, domain, tunnel_domain, traefik_labels, whitelist, image_tag, notes

**Status:** ✅ Complete

---

### CP1-T1: Install Tailscale on Ghost

**Summary:** Install and configure Tailscale on ghost to enable cross-host networking.

**Actions:**
1. Install Tailscale on ghost: `curl -fsSL https://tailscale.com/install.sh | sh`
2. Authenticate: `sudo tailscale up --accept-routes`
3. Enable subnet router if needed for LAN access
4. Note the Tailscale IP for later use

**Status:** ✅ Already installed (100.64.184.5)

---

### CP1-T2: Install Tailscale on Babyblue

**Summary:** Install and configure Tailscale on babyblue to connect to the same tailnet.

**Actions:**
1. Install Tailscale on babyblue: `curl -fsSL https://tailscale.com/install.sh | sh`
2. Authenticate with the same tailnet
3. Verify both hosts are visible: `tailscale status`

**Status:** ✅ Already installed (babyblue-aurora at 100.89.224.92)

---

### CP1-T3: Verify Cross-Host Communication

**Summary:** Test that containers on one host can reach services on the other host via Tailscale.

**Verification:**
```bash
# From a container on ghost, test reaching babyblue's ollama
docker run --rm curlimages/curl curl http://babyblue-aurora:11434

# From a container on babyblue, test reaching ghost's services
docker run --rm curlimages/curl curl http://ghost:9093
```

**Status:** ✅ Verified working
- ollama (babyblue-aurora:11434) → 200
- open-webui (babyblue-aurora:3002) → 200
- linkding (ghost:9093) → 302

---

### CP2-T1: Research Traefik v3 Migration

**Summary:** Understand changes between v2.4 and v3 before upgrading.

**Key changes:**
- TOML config deprecated, prefer YAML or CRD
- `file` provider syntax changes
- Middleware chain syntax simplified
- EntryPoint format updated
- Breaking changes in routing

**Status:** ⬜ Pending

---

### CP2-T2: Update Traefik Docker Compose

**Summary:** Update image tag and any v2-specific configs.

**Current:** `image: traefik:v2.4`
**Target:** `image: traefik:v3.x` (latest stable)

**Actions:**
1. Update image tag in compose
2. Check for deprecated options
3. Test container starts

**Status:** ⬜ Pending

---

### CP2-T3: Migrate traefik.toml

**Summary:** Update TOML to YAML or adapt syntax for v3.

**Files to migrate:**
- `compose/ghost/traefik/private/traefik.toml` → `traefik.yml`

**Key changes:**
- TOML tables → YAML structure
- Check deprecated options
- Review plugins compatibility

**Status:** ⬜ Pending

---

### CP2-T4: Migrate config.yml

**Summary:** Update dynamic config for v3 syntax if needed.

**Actions:**
1. Review current config.yml
2. Update any v2-specific syntax
3. Test with `traefik --dry-run` or similar

**Status:** ⬜ Pending

---

### CP2-T5: Test All Routes

**Summary:** Verify all services still route correctly after upgrade.

**Verification:**
```bash
curl -I https://<service>.paynepride.com
```

**Status:** ⬜ Pending

---

### CP3-C1: Audit Compose Files

**Summary:** Review all compose files for consistency and best practices.

**Audit findings:**
- 31/53 files already use phantomlink
- Label format inconsistent: `"true"` (56) vs `true` (4)
- Restart policy: `always` (10) vs `unless-stopped`
- TZ format varies: quoted vs unquoted
- 107/53 files define explicit container_name

**Checklist:**
- [x] Audit complete
- [ ] Fix label quoting (4 files use unquoted `true`)
- [ ] Standardize restart policy
- [ ] Standardize TZ format

**Status:** ✅ Complete

---

### CP3-C2: Fix Label Quoting</**Summary:** Fix inconsistent `traefik.enable` formatting.

**Files to fix:**
- ghost/monitoring-visibility/docker-compose.yml (2)
- ghost/nextcloud/docker-compose.yml (1)
- ghost/archivebox/docker-compose.yml (1)

**Status:** ⬜ Pending

---

### CP3-C2: Standardize Patterns

**Summary:** Ensure consistent patterns across all stacks.

**Common patterns to standardize:**
- Networks: selective (see CP3-C3)
- Volumes: named volumes vs bind mounts
- Labels: traefik label format (use `"true"`)
- Environment: env_file usage

**Status:** ✅ Complete

---

### CP3-C2: Fix Label Quoting

**Summary:** Fix inconsistent `traefik.enable` formatting.

**Files fixed:**
- ghost/nextcloud/docker-compose.yml
- ghost/archivebox/docker-compose.yml
- ghost/monitoring-visibility/docker-compose.yml (2 instances)

**Status:** ✅ Complete

---

### CP3-C3: Network Rearchitecture

**Summary:** Define network architecture for security and simplicity.

**Decision:** Keep Traefik on `network_mode: host` to maintain cross-node routing via Tailscale. This provides:
- Traefik reaches all containers (Docker + Tailscale)
- Only labeled services are externally exposed
- Cross-node services work (ghost → babyblue via Tailscale DNS)
- No phantomlink changes needed

**Status:** ✅ Complete

---

### CP3-C4: Create Just Recipes

**Summary:** Define network architecture for security and simplicity.

**Decision:** Keep Traefik on `network_mode: host` to maintain cross-node routing via Tailscale. This provides:
- Traefik reaches all containers (Docker + Tailscale)
- Only labeled services are externally exposed
- Cross-node services work (ghost → babyblue via Tailscale DNS)
- No phantomlink needed for routing (only for isolation if desired)

**Conclusion:** No structural changes needed to compose files.

**Status:** ✅ Complete

---

### CP3-C4: Just Recipes

**Summary:** Create comprehensive just recipes for compose operations.

**Commands needed:**
- deploy
- restart  
- logs
- pull
- outdated (check for updates)
- ps (list containers)

**Status:** ⬜ Pending

---

## Open Questions

1. Should apprise, beszel, duplicati be removed entirely or kept for potential future use?
2. [RESOLVED] Traefik upgraded to v3.6.12
3. Should traefik config be TOML or YAML going forward? (TOML works fine in v3)
4. Should monitoring be consolidated across hosts at some point?

---

## References

- Traefik v3 migration: https://doc.traefik.io/traefik/migration/v2-to-v3/
- Current traefik config: `compose/ghost/traefik/private/config.yml`
- Tailscale install: https://tailscale.com/download

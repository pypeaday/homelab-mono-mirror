# Flow state — halloween-timeline — COMPLETE

**Goal:** Ship a beautiful interactive Halloween-history timeline to halloween.paynepride.com — Christian thread highlighted, cultural influences (Samhain → Día de los Muertos) shown, with a clear answer to "when did mocking the devil start." ✅ DONE — live at https://halloween.paynepride.com

**Now:** complete

**Done:**
- 27-event timeline across 5 eras, culture filter chips (incl. a dedicated ☩ Devil thread filter), expandable cards with source links, ember canvas hero, scroll-driven spine
- Devil-mockery answer researched + hedged: motif ancient (Athanasius ~360 "sparrow for our amusement", Nyssa ~385 fishhook) → medieval stage laughter (mystery plays, risus paschalis, Julian of Norwich 1373) → Reformation (Luther "jeer and flout him", More 1534) → Screwtape 1942 → **costumes-as-mockery claim first clearly stated by James Jordan, Aug 1996** — real theology, not documented medieval fact
- DotD enriched from Florentine Codex feasts → fusion nuance → Catrina (1912/1913/Rivera 1947) → Self Help Graphics 1970s → UNESCO 2008 → Spectre-parade 2016
- Deployed: image on ghost registry, compose in homelab-mono, traefik router live, Komodo stack `halloween-timeline` (running), services.csv row, PROJECTS.md row, AGENTS.md runbook
- Repos: git-ghost:nic/halloween-timeline (pushed), homelab-mono commit 0ac95e7
- RESEARCH.md in app repo holds all sourced findings + contested claims

**Parked:**
- Could add OG/social meta image later
- Local preview server still on :8123 (python http.server, kill when done)

**Decisions:**
- Static site, no build step — Dockerfile is just nginx:alpine COPY
- Subdomain halloween.paynepride.com (apex hosts other things)
- Learned: traefik docker-provider registration lags ~60s behind a fresh container's healthcheck — a 404 right after `compose up` is normal; check `/api/http/routers` before debugging
- km CLI can't create stacks — used Core API `POST /write/CreateStack` + `UpdateStack` with X-Api-Key/Secret from ~/.config/komodo/komodo.cli.toml

## Round 2 (done)
- Worldwide dead festivals shipped as a "parallel traditions" gallery (13 cards) — not timeline events, since they're convergence not influence
- Timeline now 38 events: Anthesteria, relic economy, purgatory erasure, Totensonntag + contested century (O'Bryan, hell houses, slasher film, Devil's/Angels' Night, Satanic Panic, trunk-or-treat)
- Luther event corrected to the documented Oct 31 MAILING (door-nailing = Melanchthon 1546, contested)
- Deployed: commit ba89f0f, image pushed, public 200 verified

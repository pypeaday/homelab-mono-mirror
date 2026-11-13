# webtop — browser desktop for Dad

`linuxserver/webtop:ubuntu-xfce` — a full XFCE desktop streamed to the browser
(KasmVNC/Selkies). Dad's laptop only runs a browser tab; everything else happens
on ghost.

- **URL**: https://dad.paynepride.com
- **Auth**: traefik `simple-auth@file` basic-auth (user `dad` in
  `traefik/private/usersFile`; password in `.env` as `WEBTOP_PASSWORD`).
  The webtop's own nginx auth_basic is intentionally OFF (`PASSWORD` env unset)
  so dad gets ONE browser prompt, then lands directly on the desktop.
- **Resources**: 10 GB mem limit, `shm_size: 2gb`, /config on
  `/tank/encrypted/docker/webtop/config` (persists desktop + ToS install).
- **Network**: `phantomlink` only, no published host port. Traefik router
  `webtop@docker` → container :3000.

## thinkorswim

Installed 2026-10-31 to `/config/thinkorswim` (persists in the volume), desktop
launcher at `/config/Desktop/thinkorswim.desktop`. First launch may show an
"untrusted launcher" shield — click "Mark Executable" once. ToS self-updates on
every launch (large first-run download is normal).

**JRE**: pinned to Temurin 21 at `/config/jre21` (inside the persistent volume)
via `/config/thinkorswim/.install4j/pref_jre.cfg`. Two gotchas learned the hard
way: (1) it must be a **full** JRE — `openjdk-*-jre-headless` lacks
`libsplashscreen.so`/`libawt_xawt.so` and ToS dies with
`HeadlessException: ... no headful library support` even with DISPLAY set;
(2) ToS 1994.x requires JRE >= 21.0.5, and install4j itself breaks on JDK >= 24.

**If the container is recreated**: ToS + JRE 21 survive in `/config` — nothing
to redo for the app itself. To *reinstall* ToS, the install4j installer needs a
container JRE <= 21 (`apt-get install -y openjdk-17-jre`), then:

```bash
docker exec -u abc webtop bash -c '
  export HOME=/config INSTALL4J_JAVA_HOME_OVERRIDE=/usr/lib/jvm/java-17-openjdk-amd64
  curl -sfLo /tmp/tos.sh https://tosmediaserver.schwab.com/installer/InstFiles/thinkorswim_installer.sh
  chmod +x /tmp/tos.sh && /tmp/tos.sh -q -dir /config/thinkorswim'
```

## Ops notes

- Traefik docker provider sometimes misses container recreates: if the router
  vanishes from `http://ghost:8083/api/http/routers`, `docker --context ghost
  restart traefik` forces a rescan.
- usersFile edits (new users) likewise need a traefik restart — it's read at
  middleware build, not per-request.
- `abc` inside the container is the desktop user; container-init apt packages
  are ephemeral (live in the image layer, not /config).

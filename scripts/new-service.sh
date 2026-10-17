#!/usr/bin/env bash
# Scaffold a new service stack following homelab conventions.
# Usage: scripts/new-service.sh <host> <name> [port] [internal_port] [--whitelist]
#   e.g. scripts/new-service.sh ghost signoz 3301 3301 --whitelist
set -euo pipefail

HOST="${1:?usage: new-service.sh <host> <name> [port] [internal_port] [--whitelist]}"
NAME="${2:?service name required}"
PORT="${3:-}"
INTERNAL="${4:-$PORT}"
WHITELIST="${5:-}"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$REPO_ROOT/compose/$HOST/$NAME"
DOMAIN="${NAME}.paynepride.com"
DATA="/tank/encrypted/docker/${NAME}-zfs"

if [ -d "$DIR" ]; then
  echo "exists already: $DIR" >&2
  exit 1
fi
mkdir -p "$DIR"

WHITELIST_LABEL=""
if [ "$WHITELIST" = "--whitelist" ]; then
  WHITELIST_LABEL="      traefik.http.routers.${NAME}.middlewares: default-whitelist@file"
fi

PORTS=""
if [ -n "$PORT" ]; then
  PORTS="    ports:
      - \"${PORT}:${INTERNAL}\"
"
fi

cat > "$DIR/docker-compose.yml" <<EOF
services:
  ${NAME}:
    image: "TODO:image:tag"
    container_name: "${NAME}"
${PORTS}    volumes:
      - ${DATA}/data:/data
    environment:
      TZ: "America/Chicago"
    env_file: .env
    restart: unless-stopped
    networks:
      - phantomlink
    labels:
      traefik.enable: "true"
      traefik.http.routers.${NAME}.rule: Host(\`${DOMAIN}\`)
      traefik.http.routers.${NAME}.tls.certresolver: letsencrypt
      traefik.http.routers.${NAME}.tls.domains[0].main: "paynepride.com"
      traefik.http.routers.${NAME}.tls.domains[0].sans: "*.paynepride.com"
      traefik.http.services.${NAME}.loadbalancer.server.port: "${INTERNAL:-TODO}"
${WHITELIST_LABEL}
networks:
  phantomlink:
    external: true
EOF

cat > "$DIR/justfile" <<EOF
deploy:
  #!/bin/bash
  set -e
  ssh ${HOST} "mkdir -p ${DATA}/data"
  docker context use ${HOST}
  docker compose up -d --force-recreate

up:
  docker --context ${HOST} compose up -d

down:
  docker --context ${HOST} compose down

restart:
  docker --context ${HOST} compose restart

logs lines="100":
  docker --context ${HOST} compose logs --tail={{lines}} -f

ps:
  docker --context ${HOST} compose ps
EOF

cat > "$DIR/.env.example" <<EOF
# Copy to .env and fill in
# TZ=America/Chicago
EOF

cat > "$DIR/README.md" <<EOF
# ${NAME}

Domain: https://${DOMAIN}
Data: ${DATA}

## First-time setup

1. Create the zfs dataset on ${HOST} (encryption/compression inherit from tank/encrypted):
   \`\`\`bash
   ssh ${HOST}
   sudo rm -rf ${DATA}   # if docker auto-created a plain dir
   sudo zfs create ${DATA#/}
   sudo chown nic:nic ${DATA}
   sudo chmod 2775 ${DATA}
   \`\`\`
2. Register for snapshots in /etc/sanoid/sanoid.conf on ${HOST} (recursive=no means
   datasets get NO snapshots without their own block → never replicate to harbor):
   \`\`\`
   [${DATA#/}]
     use_template = docker
     recursive = no
   \`\`\`
   Then \`sudo systemctl reload-or-restart sanoid\` and mirror the block into
   zfs-ops/hosts/${HOST}/sanoid.conf.
3. \`cp .env.example .env\` and fill in secrets
4. \`just deploy\`
EOF

# services.csv registry
CSV="$REPO_ROOT/compose/services.csv"
if ! grep -q "^${NAME},${HOST}," "$CSV" 2>/dev/null; then
  WL="no"; [ "$WHITELIST" = "--whitelist" ] && WL="yes"
  echo "${NAME},${HOST},${PORT:-},${INTERNAL:-},${DOMAIN},http://${HOST}:${PORT:-},yes,${WL},TODO," >> "$CSV"
  echo "services.csv: added row"
fi

echo
echo "Created $DIR"
echo
echo "Next steps:"
echo "  1. dataset + perms (on ${HOST}):"
echo "       sudo zfs create ${DATA#/} && sudo chown nic:nic ${DATA} && sudo chmod 2775 ${DATA}"
echo "  2. sanoid: add [${DATA#/}] with 'use_template = docker' to /etc/sanoid/sanoid.conf on ${HOST}"
echo "     (no block = no snapshots = never replicates to harbor)"
echo "  3. fill image + secrets:        edit $DIR/docker-compose.yml, cp .env.example .env"
echo "  4. deploy:                      cd $DIR && just deploy"
echo "  5. verify:                      curl -sI https://${DOMAIN} | head -1"

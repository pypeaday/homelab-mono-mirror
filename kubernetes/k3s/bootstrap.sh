#!/bin/bash
set -euo pipefail

CONFIG=hosts.yaml

yq_check() {
  if ! command -v yq >/dev/null 2>&1; then
    echo "yq is required. Install with: pip install yq or go install yq."
    exit 1
  fi
}

resolve_test() {
  if ! ping -c1 "$1" >/dev/null 2>&1; then
    echo "Cannot resolve $1 (is your Tailscale up?)"
    exit 1
  fi
}

render_template() {
  # envsubst can't handle YAML keys well, so use perl-for-env templating
  perl -pe 's/\$\{(\w+)\}/$ENV{$1}/g' "$1"
}

yq_check

SERVER_HOST=$(yq '.server.host' "$CONFIG")
SERVER_USER=$(yq '.server.user' "$CONFIG")
SERVER_LAN=$(yq '.server.lan_ip' "$CONFIG")

resolve_test "$SERVER_HOST"

export HOST="$SERVER_HOST"
export USER="$SERVER_USER"
export NODE_IP="$SERVER_LAN"

# Render server.yaml
render_template server.yaml >server.yaml.rendered
mv server.yaml.rendered server.yaml

# Render server install script
render_template templates/server-install.sh.tpl >server-install.sh
chmod +x server-install.sh

echo "Installing k3s server..."
./server-install.sh

echo "Joining agents..."

AGENT_COUNT=$(yq '.agents | length' "$CONFIG")
for i in $(seq 0 $((AGENT_COUNT - 1))); do
  export HOST=$(yq ".agents[$i].host" "$CONFIG")
  export USER=$(yq ".agents[$i].user" "$CONFIG")
  export NODE_IP=$(yq ".agents[$i].lan_ip" "$CONFIG")
  export SERVER_HOST="$SERVER_HOST"

  resolve_test "$HOST"

  render_template agent.yaml >agent.yaml.rendered
  mv agent.yaml.rendered agent.yaml

  render_template templates/agent-install.sh.tpl >"agent-install-$i.sh"
  chmod +x "agent-install-$i.sh"

  ./agent-install-$i.sh
done

echo "Cluster ready."

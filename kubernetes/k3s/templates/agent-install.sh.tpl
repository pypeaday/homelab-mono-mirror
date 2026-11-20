
#!/bin/bash
set -euo pipefail

k3sup join \
  --server-host "${SERVER_HOST}" \
  --host "${HOST}" \
  --user "${USER}" \
  --k3s-extra-args "--node-ip ${NODE_IP}"
  
# Push agent.yaml
scp agent.yaml "${USER}@${HOST}:/etc/rancher/k3s/config.yaml"
ssh "${USER}@${HOST}" "sudo systemctl restart k3s-agent"


#!/bin/bash
set -euo pipefail

# Uses k3sup to install the server
k3sup install \
  --host "${HOST}" \
  --user "${USER}" \
  --tls-san "${HOST}" \
  --k3s-extra-args "--node-ip ${NODE_IP} --advertise-address ${NODE_IP}" \
  --local-path kubeconfig

# Push server.yaml
scp server.yaml "${USER}@${HOST}:/etc/rancher/k3s/config.yaml"
ssh "${USER}@${HOST}" "sudo systemctl restart k3s"

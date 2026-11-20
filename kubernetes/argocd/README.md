# ArgoCD App of Apps — Homelab K8s Migration

Migrates `compose/ghost` Docker Compose stacks to Kubernetes via ArgoCD's App of Apps pattern on k3s.

## Architecture

```
root-app.yaml (App of Apps)
 ├── apps/
 │    ├── infrastructure/     ArgoCD Application CRDs for platform services
 │    │   ├── argocd.yaml     (helm: argo-cd)
 │    │   ├── cert-manager.yaml (helm: cert-manager + CRDs)
 │    │   ├── sealed-secrets.yaml (helm: sealed-secrets)
 │    │   └── cluster-resources.yaml (namespaces, ClusterIssuer, middleware)
 │    └── workloads/          ArgoCD Application CRDs → each uses homelab-app chart
 │        ├── actual.yaml
 │        ├── eigenfocus.yaml
 │        ├── freshrss.yaml
 │        ├── gotify.yaml
 │        ├── grist.yaml
 │        ├── homebox.yaml
 │        ├── linkding.yaml
 │        ├── searxng.yaml
 │        └── stirlingtools.yaml
 ├── charts/
 │    └── homelab-app/        Generic Helm chart for single-container workloads
 │        ├── Chart.yaml
 │        ├── values.yaml     (defaults)
 │        └── templates/      (deployment, service, ingress, sealed-secret)
 ├── values/                  Per-app values files
 │    ├── actual.yaml
 │    ├── eigenfocus.yaml
 │    ├── freshrss.yaml
 │    ├── gotify.yaml
 │    ├── grist.yaml
 │    ├── homebox.yaml
 │    ├── linkding.yaml
 │    ├── searxng.yaml
 │    └── stirlingtools.yaml
 └── manifests/
      └── infrastructure/     Cluster-wide resources (applied by cluster-resources app)
```

## What's Included (Initial Migration Batch)

These were chosen because they're simple (no docker.sock, no host networking, no GPU):

| App | Compose Source | Secrets | Notes |
|-----|---------------|---------|-------|
| actual | `compose/ghost/actual` | none | Budget server |
| eigenfocus | `compose/ghost/eigenfocus` | `.env` | Task manager |
| freshrss | `compose/ghost/freshrss` | none | RSS reader |
| gotify | `compose/ghost/gotify` | none | Push notifications |
| grist | `compose/ghost/grist` | none | Spreadsheet |
| homebox | `compose/ghost/homebox` | none | Home inventory |
| linkding | `compose/ghost/linkding` | `.env` | Bookmark manager |
| searxng | `compose/ghost/searxng` | `.env` | Search engine + redis sidecar |
| stirlingtools | `compose/ghost/stirlingtools` | none | PDF tools |

## What's NOT Migrated Yet

Complex stacks that need more planning:
- **immich** — multi-container with postgres+redis+ML, hardware transcoding
- **nextcloud** — mariadb+redis, large volume mounts
- **paperless-ngx** — postgres+redis+AI sidecar
- **forgejo** — git server + CI runners + DinD
- **media-stack** — jellyfin (hardware accel), audiobookshelf, pinchflat, ubooquity
- **arrs** — 10+ containers, VPN via gluetun, transmission
- **traefik** — replaced by k3s built-in Traefik + cert-manager
- **portainer/beszel** — replaced by k8s-native tooling
- **monitoring** — replaced by k8s-native observability (glances/netdata → Prometheus stack)
- **affine/postiz/karakeep/domain-locker/temporalio** — multi-container with DBs

## Prerequisites

1. **k3s** running on ghost (use `../k3s/bootstrap.sh`)
2. **kubectl** configured (`export KUBECONFIG=/etc/rancher/k3s/k3s.yaml`)
3. **kubeseal** CLI installed for creating sealed secrets
4. **DNS** — `*.paynepride.com` pointing to ghost's IP (already in place via Traefik)

## Bootstrap

### 1. Install ArgoCD (one-time manual step)

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Get the initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

### 2. Configure repo access

```bash
# If using a private repo, create a repo secret
kubectl -n argocd create secret generic homelab-repo \
  --from-literal=type=git \
  --from-literal=url=https://github.com/YOUR_USER/homelab-mono.git \
  --from-literal=username=YOUR_USER \
  --from-literal=password=YOUR_PAT \
  --label argocd.argoproj.io/secret-type=repository
```

### 3. Apply the root App of Apps

```bash
# IMPORTANT: First edit root-app.yaml and all apps/*.yaml to replace
# YOUR_USER with your actual GitHub username / git remote URL.
kubectl apply -f kubernetes/argocd/root-app.yaml
```

ArgoCD will now recursively discover and deploy all Application CRDs in `apps/`.

### 4. Seal your secrets

After sealed-secrets is running, seal each `.env` file:

```bash
# Example for linkding
kubectl create secret generic linkding-secrets \
  --namespace homelab \
  --from-env-file=compose/ghost/linkding/.env \
  --dry-run=client -o yaml | \
  kubeseal \
    --controller-name=sealed-secrets-controller \
    --controller-namespace=sealed-secrets \
    --format yaml \
  > kubernetes/argocd/sealed-secrets/linkding.yaml

# Repeat for eigenfocus, searxng, and any future apps with secrets
```

Commit the sealed secrets to git — they're safe to store in version control.

### 5. Configure cert-manager

Create the Cloudflare API token secret (or adjust for your DNS provider):

```bash
kubectl create secret generic cloudflare-api-token \
  --namespace cert-manager \
  --from-literal=api-token=YOUR_CLOUDFLARE_API_TOKEN
```

Edit `manifests/infrastructure/cluster-issuer.yaml` if you use a different DNS provider.

## Key Differences from Docker Compose

| Concern | Compose | K8s |
|---------|---------|-----|
| **Reverse proxy** | Traefik labels on containers | Ingress resources + k3s Traefik |
| **TLS** | Traefik ACME certresolver | cert-manager ClusterIssuer |
| **Secrets** | `.env` files on disk | SealedSecrets (encrypted in git) |
| **Networking** | `phantomlink` Docker network | k8s Service + ClusterIP |
| **Storage** | bind mounts to `/tank/...` | hostPath volumes (same ZFS paths) |
| **Updates** | manual `docker compose pull` | ArgoCD auto-sync + image updater |
| **IP whitelist** | Traefik `default-whitelist@file` | Traefik Middleware CRD |
| **Restart policy** | `unless-stopped` | k8s restartPolicy (always by default) |

## Storage Strategy

All persistent data stays on existing ZFS paths under `/tank/encrypted/...` via `hostPath` volumes.
This means:
- **Zero data migration** needed — k8s pods read the same files
- Only works on a single-node cluster (which ghost is)
- If you add nodes later, switch to NFS/Longhorn/local-path-provisioner with node affinity

## Adding a New App

1. Create `values/<app-name>.yaml` with image, port, volumes, env, ingress host, etc.
2. Create `apps/workloads/<app-name>.yaml` ArgoCD Application CRD pointing to `charts/homelab-app` with `helm.valueFiles: [../../values/<app-name>.yaml]`
3. Commit and push — ArgoCD picks it up automatically

The generic `charts/homelab-app` chart handles: Deployment (Recreate strategy), Service (ClusterIP), Ingress (Traefik + wildcard TLS), optional SealedSecret, optional sidecars.

## Image Updates

Consider adding [ArgoCD Image Updater](https://argocd-image-updater.readthedocs.io/) to automatically
track `:latest` tags and create update commits. This replaces the manual `docker compose pull && up -d` workflow.

## TODO

- [ ] Replace `YOUR_USER` in all Application CRDs with actual git remote
- [ ] Bootstrap k3s on ghost
- [ ] Install ArgoCD
- [ ] Seal secrets for linkding, eigenfocus, searxng
- [ ] Configure cert-manager DNS provider secret
- [ ] Test first app (e.g., gotify — simplest, no secrets)
- [ ] Set up ArgoCD Image Updater for automatic container updates
- [ ] Migrate next batch: affine, karakeep, domain-locker
- [ ] Evaluate Prometheus/Grafana stack to replace glances/netdata

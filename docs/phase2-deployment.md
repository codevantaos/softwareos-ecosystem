# Phase 2 Deployment — Harbor + Argo CD

**Deployed**: 2026-02-26T06:04 (UTC+8)  
**Cluster**: eco-production | asia-east1 | GKE v1.34.3

---

## Harbor (Container Registry)

| Item | Value |
|------|-------|
| Namespace | `harbor` |
| Helm Chart | `harbor/harbor` v1.18.2 |
| App Version | Harbor 2.14.2 |
| Internal URL | `http://harbor.harbor.svc.cluster.local` |
| Admin User | `admin` |
| Admin Password | `Eco@Harbor2026` (stored in GitHub Secret: `HARBOR_ADMIN_PASSWORD`) |
| Registry Storage | 20Gi (standard-rwo) |
| Trivy Scanner | Enabled |
| Metrics | Enabled |

### Harbor Pods (9/9 Running)
- `harbor-core` — API server
- `harbor-database` — PostgreSQL
- `harbor-exporter` — Prometheus metrics
- `harbor-jobservice` — Async jobs
- `harbor-nginx` — Reverse proxy
- `harbor-portal` — Web UI
- `harbor-redis` — Cache
- `harbor-registry` — OCI registry (2 containers)
- `harbor-trivy` — Vulnerability scanner

---

## Argo CD (GitOps Controller)

| Item | Value |
|------|-------|
| Namespace | `argocd` |
| Helm Chart | `argo/argo-cd` v9.4.4 |
| App Version | Argo CD v3.3.2 |
| Internal URL | `http://argocd-server.argocd.svc.cluster.local` |
| Admin User | `admin` |
| Admin Password | Stored in GitHub Secret: `ARGOCD_ADMIN_PASSWORD` |
| Mode | Insecure (TLS terminated at ingress) |

### Argo CD Pods (7/7 Running)
- `argocd-application-controller` — Reconciliation loop
- `argocd-applicationset-controller` — ApplicationSet management
- `argocd-dex-server` — OIDC/SSO
- `argocd-notifications-controller` — Alerts
- `argocd-redis` — Cache
- `argocd-repo-server` — Git repo access
- `argocd-server` — API + Web UI

### Argo CD Application
- **Name**: `softwareos-base-platforms`
- **Source**: `https://github.com/indestructibleorg/softwareos-base` (branch: main, path: platforms/)
- **Destination**: `eco-production` namespace
- **Sync**: Automated (prune + selfHeal)
- **Status**: Synced / Healthy

---

## GitHub Secrets Updated
- `ARGOCD_ADMIN_PASSWORD` — Argo CD admin password
- `HARBOR_ADMIN_PASSWORD` — Harbor admin password
- `HARBOR_URL` — Harbor internal service URL
- `ARGOCD_URL` — Argo CD internal service URL

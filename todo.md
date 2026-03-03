# softwareos-base — CircleCI Self-Hosted Runner Setup

## Phase 1: Create CircleCI Configuration
- [x] Create `.circleci/config.yml` with self-hosted runner configuration
- [x] Configure `eco/base` resource class for container runner

## Phase 2: Create Kubernetes Manifests
- [x] Create namespace manifest
- [x] Create ConfigMap with runner configuration
- [x] Create Secret manifest template
- [x] Create Deployment manifest
- [x] Create RBAC resources (ServiceAccount, Role, ClusterRole)
- [x] Create deployment script
- [x] Fix `k8s/circleci/deployment.yaml` structure and offline-validate manifest integrity

## Phase 3: Documentation
- [x] Create comprehensive setup guide

## Phase 4: Deployment (Pending)
- [ ] P0 — Get CircleCI runner token from https://app.circleci.com/settings/user/tokens (external dependency)
- [ ] P1 — Set CIRCLECI_RUNNER_TOKEN environment variable
- [ ] P1 — Run deployment script: `./scripts/deploy-circleci-runner.sh`
- [ ] P2 — Verify runner connectivity
- [ ] P2 — Test with CircleCI pipeline

## Pending Tasks (from previous session)
- [ ] P0 — SSD Quota Increase — Asia-east1 region (250GB → 500GB) (external dependency)
- [ ] P1 — OAuth Consent Screen — Configure OAuth 2.0 client for IAP (external dependency)
- [ ] P1 — Production Cluster — Waiting for quota approval (blocked by quota)
# GitHub PAT Security Best Practices Guide

**Version:** 1.0.0
**Owner:** eco-ops-team
**Last Updated:** 2026-02-26
**Applies To:** indestructibleorg/softwareos-base and all related repositories

---

## 1. Token Type Selection

| Scenario | Recommended Type | Reason |
|----------|-----------------|--------|
| CI/CD automation (single repo) | **Fine-grained PAT** | Scoped to specific repo + permissions |
| CI/CD automation (org-wide) | **GitHub App** | No expiry, auditable, revocable per installation |
| Human developer access | **Fine-grained PAT** | Explicit expiry, least-privilege |
| Legacy system integration | Classic PAT (temporary) | Only if fine-grained not supported; migrate ASAP |

**Rule:** Never use Classic PATs (`ghp_*`) for new integrations. Classic PATs grant broad scope and have no repo-level restriction.

---

## 2. Least-Privilege Scoping

### Fine-grained PAT — Minimum Required Permissions for softwareos-base CI/CD

| Permission | Level | Justification |
|------------|-------|---------------|
| `contents` | Read + Write | Push code, update files |
| `workflows` | Write | Push `.github/workflows/` changes |
| `issues` | Write | Auto-create incident issues |
| `pull_requests` | Read | Post PR comments from gates |
| `metadata` | Read | Required by all tokens |

**All other permissions: None.**

### Repository Scope

Scope fine-grained PATs to **only the repositories that require access**. Do not select "All repositories" unless explicitly required.

---

## 3. Expiry Policy

| Token Category | Maximum Lifetime | Rotation Trigger |
|----------------|-----------------|------------------|
| CI/CD automation PAT | **90 days** | Automated alert at T-14 days |
| Developer PAT | **30 days** | Manual renewal |
| Emergency access PAT | **24 hours** | Single-use, revoke immediately after |

**Rule:** All PATs must have an explicit expiry date. No-expiry tokens are prohibited.

---

## 4. Storage and Transmission

### Permitted Storage Locations

| Location | Permitted | Notes |
|----------|-----------|-------|
| GitHub Actions Secrets | **Yes** | Encrypted at rest, masked in logs |
| HashiCorp Vault | **Yes** | With dynamic secrets preferred |
| `.env` files (gitignored) | **Local dev only** | Never commit |
| Kubernetes Secrets (sealed) | **Yes** | Use Sealed Secrets or External Secrets Operator |

### Prohibited Storage Locations

- Source code (any file, any branch)
- Chat messages, tickets, or email (plaintext)
- CI/CD logs (ensure masking is active)
- Shared documents or wikis
- Environment variables in container images

**Rule:** Any PAT transmitted in plaintext (including chat) must be rotated within 24 hours.

---

## 5. Rotation Procedure

### Standard Rotation (90-day cycle)

```
1. Generate new fine-grained PAT at:
   https://github.com/settings/personal-access-tokens/new
   - Same permissions as existing token
   - Expiry: today + 90 days

2. Update GitHub Actions secret:
   Settings → Secrets and variables → Actions
   → Update PAT_TOKEN (or equivalent)

3. Update PAT_EXPIRY_DATE secret:
   Value: YYYY-MM-DD (new expiry date)

4. Verify CI pipeline succeeds with new token

5. Revoke old token:
   https://github.com/settings/personal-access-tokens
   → Delete old token

6. Update pat-audit-report.md with new token metadata
```

### Emergency Rotation (token compromised)

```
1. IMMEDIATELY revoke compromised token:
   https://github.com/settings/tokens (Classic)
   https://github.com/settings/personal-access-tokens (Fine-grained)

2. Generate replacement token (same permissions)

3. Update all secrets that used the compromised token

4. Audit GitHub audit log for unauthorized API calls:
   https://github.com/organizations/indestructibleorg/settings/audit-log
   Filter: token=<compromised_prefix>

5. Open security incident issue in softwareos-base with:
   - Token prefix (never full value)
   - Time of compromise discovery
   - API calls made with compromised token (from audit log)
   - Remediation steps taken

6. Update pat-audit-report.md
```

---

## 6. Automated Monitoring

The `pat-expiry-check.yml` workflow enforces the following:

| Check | Frequency | Action |
|-------|-----------|--------|
| T-14 days before expiry | Daily 07:00 UTC | `::warning::` annotation + GitHub Issue |
| T-7 days before expiry | Daily 07:00 UTC | GitHub Issue (HIGH priority) |
| Token expired | Daily 07:00 UTC | GitHub Issue (CRITICAL) + workflow fails |

### Required Secrets

Set these in `indestructibleorg/softwareos-base` → Settings → Secrets → Actions:

| Secret | Format | Example |
|--------|--------|---------|
| `PAT_EXPIRY_DATE` | `YYYY-MM-DD` | `2026-05-27` |
| `PAT_TOKEN_ID` | First 30 chars of token | `github_pat_11B52RIHI0HntIa9MW543j` |

---

## 7. Audit Requirements

All PAT lifecycle events must be documented in `docs/pat-audit-report.md`:

| Event | Required Fields |
|-------|----------------|
| Token created | Date, type, permissions, expiry, owner |
| Token rotated | Old token prefix, new token prefix, rotation date, reason |
| Token revoked | Token prefix, revocation date, reason |
| Token compromised | Token prefix, discovery date, scope of exposure, remediation |

**Retention:** PAT audit records must be retained for 12 months minimum (SOC2 / ISO27001 requirement).

---

## 8. GitHub App Migration Path

For long-term automation, migrate from PAT to **GitHub App**:

| Advantage | Detail |
|-----------|--------|
| No expiry | App installations do not expire |
| Per-repo installation | Granular access control |
| Audit trail | All API calls attributed to app, not user |
| Revocable | Revoke per-repo without affecting other repos |

Migration steps:
1. Create GitHub App at `github.com/organizations/indestructibleorg/settings/apps/new`
2. Set permissions identical to current PAT scope
3. Install app on `indestructibleorg/softwareos-base`
4. Generate installation token in CI via `actions/create-github-app-token`
5. Revoke PAT after successful migration

---

## 9. Compliance Mapping

| Rule | OPERATIONS.md | SOC2 | ISO27001 |
|------|--------------|------|----------|
| Explicit expiry on all tokens | Rule-03 (analogy) | CC6.1 | A.9.4.3 |
| Least-privilege scoping | Rule-01 | CC6.3 | A.9.2.3 |
| Rotation within 90 days | §3 above | CC6.1 | A.9.4.3 |
| Immediate rotation on compromise | §5 above | CC7.3 | A.16.1.5 |
| Audit trail for all lifecycle events | §7 above | CC4.1 | A.12.4.1 |

---

*Violations of this guide must be treated as security incidents and reported via the standard incident process.*

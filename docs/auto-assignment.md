# Auto-Assignment System

## Overview

This repository implements a fully automated issue and pull request assignment system with:
- **Preview mode**: Decision evidence generation without enforcement
- **Enforce mode**: Automatic assignment with self-healing retry logic
- **SLA-based escalation**: Automatic escalation when response times exceed thresholds
- **Governance gates**: Hard gates to prevent misconfiguration
- **Integration**: Slack notifications and ArgoCD health checks

## Architecture

### Core Components

1. **MAINTAINERS.yaml** - Team topology, SLA, and escalation paths
2. **CODEOWNERS** - Ownership boundaries (highest priority)
3. **routing-rules.yaml** - Routing strategy (labels, files, keywords, default)
4. **Auto-assign tools** - Python modules for decision making and execution

### Workflows

- `autoassign-preview.yml` - Preview mode (evidence only)
- `autoassign-enforce.yml` - Enforce mode (applies assignments)
- `autoassign-retry.yml` - Self-healing retry worker
- `autoassign-escalate.yml` - SLA-based escalation
- `governance-verify.yml` - Hard gate for configuration changes
- `argocd-health.yml` - ArgoCD health monitoring

## Teams

- **triage** - Default owner, 12h first response, 72h review
- **frontend** - React/UX/UI, 24h first response, 72h review
- **backend** - API/DB, 24h first response, 72h review
- **docs** - Documentation, 24h first response, 72h review
- **security** - Security/Supply Chain, 6h first response, 24h review
- **infra-devops** - Infra/DevOps, 12h first response, 48h review

## Routing Rules

Priority order (lower = higher priority):

1. Security by label (priority 10)
2. Security by keyword (priority 20)
3. Infra by label (priority 30)
4. Docs by label (priority 40)
5. Frontend by files (priority 100)
6. Backend by files (priority 110)
7. Docs by files (priority 120)
8. Default fallback (priority 1000)

## Self-Healing Features

### Degradation Handling

When PR files API fails:
- System degrades gracefully (no assignment)
- Marks issue with `autoassign-degraded` label
- Schedules retry via `autoassign-retry` label
- Retry worker attempts with exponential backoff
- Maximum 12 retries (~2 hours) before circuit opens

### Escalation

Every 10 minutes:
- Checks open issues/PRs against SLA thresholds
- Escalates to oncall if:
  - No assignees after `first_response_hours`
  - Stale after `review_hours` idle time
- Adds assignees and requests reviewers
- Posts escalation comment

## Evidence and Auditing

Every assignment generates:
- `autoassign.evidence.json` artifact
- GitHub comment with trace ID
- Decision traceability:
  - Matched rules
  - Ranked candidates with scores
  - Ownership signals
  - Degradation notes (if applicable)

## Configuration

### Mode Switching

Edit `routing-rules.yaml`:

```yaml
settings:
  mode: preview  # or enforce
```

- `preview`: Evidence only, no assignments
- `enforce`: Full automatic assignment

### Required Secrets

- `GITHUB_TOKEN` - Provided by GitHub Actions
- `SLACK_WEBHOOK_URL` - Optional Slack notifications
- `ARGOCD_SERVER` - Optional ArgoCD server URL
- `ARGOCD_TOKEN` - Optional ArgoCD API token
- `ARGOCD_APP` - Optional ArgoCD application name

## Governance

### Hard Gates

The `governance-verify.yml` workflow enforces:

1. MAINTAINERS.yaml must have valid teams
2. Default team must exist
3. Routing rules must have exactly one default (last rule)
4. Priority must be sorted ascending
5. All team_id references must be valid
6. CODEOWNERS must include `* @codevantaeco/triage`

### Branch Protection

Recommended settings:
- Enable `governance-verify` as required check
- Require Code Owner approval for governance files
- Require status checks to pass before merging

## Testing

### Preview Mode Testing

1. Create an issue or PR
2. Check workflow `autoassign-preview` runs
3. Review evidence artifact
4. Verify comment shows team and assignees

### Enforce Mode Testing

1. Switch `routing-rules.yaml` to `mode: enforce`
2. Create issue/PR with various labels/files
3. Verify automatic assignment
4. Check evidence and comments

### Degradation Testing

1. Temporarily break PR files API access
2. Create PR
3. Verify degraded comment and labels
4. Wait for retry worker (10 min)
5. Verify retry attempts with backoff

### Escalation Testing

1. Create issue without assignees
2. Wait for `first_response_hours` (reduce for testing)
3. Verify escalation to oncall
4. Check escalation comment

## Troubleshooting

### Assignments Not Happening

1. Check `routing-rules.yaml` mode is `enforce`
2. Verify workflow logs in Actions tab
3. Check evidence artifact for decision details
4. Verify team members exist in MAINTAINERS.yaml

### Degradation Loop

1. Check retry worker logs
2. Verify PR files API is accessible
3. Check retry count in comments
4. Verify circuit hasn't opened (max retries)

### Escalation Not Triggering

1. Verify SLA thresholds in MAINTAINERS.yaml
2. Check issue/PR timestamps
3. Verify escalation workflow runs every 10 min
4. Check workflow logs

## Maintenance

### Adding New Team Members

Edit `MAINTAINERS.yaml`:

```yaml
teams:
  - id: frontend
    members: ["user1", "user2", "new-user"]
```

### Changing SLA Thresholds

Edit `MAINTAINERS.yaml`:

```yaml
teams:
  - id: security
    sla:
      first_response_hours: 4  # Changed from 6
      review_hours: 12         # Changed from 24
```

### Adding New Routing Rules

Edit `routing-rules.yaml`:

```yaml
rules:
  - id: new-rule
    priority: 50  # Must be between existing priorities
    when:
      any_labels: ["new-label"]
    route:
      team_id: backend
```

**Important**: Keep priority sorted ascending and default rule last.

## Security Considerations

- Token is never written to files
- All API calls use GitHub Actions token
- Evidence artifacts retained for 90 days
- Degradation prevents incorrect assignments
- Circuit breaker prevents infinite retries

## Future Enhancements

Possible additions:
- Load-based candidate ranking
- Historical contribution analysis
- Multi-team routing
- Custom escalation policies
- Integration with Jira/Linear
- Dashboard for assignment metrics
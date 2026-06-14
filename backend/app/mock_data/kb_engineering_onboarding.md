# Contoso — Engineering Onboarding & Runbook (Platform Team)

## Day 1 Setup
1. Pick up your hardware from IT (MacBook Pro M-series or Dev Box on Azure).
2. Join the SSO groups: `eng-all`, `platform-team`, and your squad group via the Access Portal.
3. Install the toolchain: `brew bundle` against the company Brewfile in `contoso/dev-setup`.
4. Request access to the monorepo `contoso/platform` (auto-approved for `eng-all`).

## Local Development
- The platform is a set of microservices orchestrated with the `cx` CLI.
- `cx up` starts the full local stack in Docker; `cx up <service>` starts a single service.
- Secrets are pulled from Azure Key Vault via `cx secrets sync` (requires VPN + `platform-team` group).
- Run `cx test` before every PR; CI will reject PRs below 80% coverage on changed files.

## Deployment
- We deploy via GitOps: merge to `main` triggers a build, which updates the image tag in `contoso/deploy`.
- Staging deploys automatically; production requires a **2-person approval** in the deploy repo.
- Rollbacks: revert the image tag commit in `contoso/deploy`; Argo CD syncs within ~3 minutes.
- Never hotfix production by hand — all changes go through the GitOps pipeline.

## On-Call & Incidents
- On-call rotation is weekly, managed in PagerDuty (`platform-primary`).
- Sev1 (customer-facing outage): page immediately, open a bridge in the `#incidents` Teams channel, assign an Incident Commander.
- Sev2 (degraded, no full outage): respond within 30 minutes during business hours.
- Every Sev1/Sev2 gets a blameless postmortem within 5 business days, filed in the `postmortems` SharePoint.

## Architecture Overview
- API gateway (Azure API Management) → service mesh → microservices (containers on AKS).
- Primary datastore: Azure SQL (transactional) + Azure Cosmos DB (high-volume events).
- Async work flows through Azure Service Bus queues.
- Observability: OpenTelemetry → Azure Monitor + Grafana dashboards.

## Common Gotchas
- "cx secrets sync fails with 403" → you're not on VPN, or not yet added to `platform-team`.
- "Local Cosmos emulator won't start on Apple Silicon" → use the cloud dev Cosmos instance with `cx up --cloud-data`.
- Flaky integration tests are tracked in the `flaky-tests` board; retry once, then file if it recurs.

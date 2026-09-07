# Errdain Beta and Live Launch Execution Plan

Status: proposed execution baseline  
Plan start: September 8, 2026  
Private beta target: November 9, 2026  
Public beta target: December 7, 2026  
Live launch target: January 12, 2027  
Assumption: one full-time technical founder with part-time design, security, and legal help

## 1. Launch definition

Errdain is ready for private beta when invited users can sign in, work only
inside their organization, generate datasets asynchronously, recover from
worker restarts, download artifacts from private object storage, create test
packages, view their own dashboards, and receive support without exposing
administrative or cross-tenant data.

Errdain is ready for live launch when those capabilities have passed a public
beta, production backup restoration and incident drills have succeeded,
security and legal launch gates are closed, and capacity/cost limits are
enforced automatically.

### Non-negotiable launch gates

- [ ] No shared API key in any public browser bundle.
- [ ] Every protected database row has an `organization_id` and ownership
      checks are tested.
- [ ] Background work survives API/container restarts and supports retries,
      idempotency, cancellation, and a dead-letter queue.
- [ ] Generated artifacts are private, short-lived, and accessed using signed
      URLs.
- [ ] Production PostgreSQL has automated backups and a successful restore
      drill.
- [ ] Production, staging, and development use different accounts, databases,
      buckets, keys, and domains.
- [ ] Admin interfaces require an explicit platform-admin role and stronger
      authentication.
- [ ] Dependency audits, tests, migrations, container builds, and smoke tests
      pass in CI/CD.
- [ ] Privacy, terms, retention, acceptable-use, security-contact, support, and
      known-issues pages are published.
- [ ] Monitoring alerts reach a human and an incident rollback has been tested.

## 2. Target production architecture

```text
errdain.com / www.errdain.com
          |
          v
Cloudflare DNS + TLS + CDN + WAF + Turnstile + rate limits
          |
          +--> app.errdain.com: Next.js frontend on Cloudflare Workers
          |
          +--> api.errdain.com: edge/API Worker
                       |
                       +--> Auth JWT verification and request context
                       +--> Cloudflare Queue producer
                       +--> Python FastAPI API/container
                                  |
                                  +--> Managed PostgreSQL
                                  +--> Durable job workers
                                  +--> Cloudflare R2 private bucket
                                  +--> Error/log/metric providers
```

### Cloudflare service choices

| Concern | Recommended service | Launch use |
|---|---|---|
| Domain, DNS, TLS | Cloudflare Registrar/DNS and Universal SSL | `errdain.com`, `app`, `api`, `status` |
| Frontend | Cloudflare Workers using the current recommended Next.js adapter path | Deploy the Next.js application globally |
| Python API/generator | Cloudflare Containers pilot | Run the existing FastAPI Docker image after load/cold-start validation |
| Backend fallback | Render, Fly.io, Railway, AWS ECS/Fargate, or Google Cloud Run behind Cloudflare | Use if Containers fails the beta workload gate |
| Artifact storage | Private Cloudflare R2 | Datasets, ZIPs, reports, manifests, ground truth |
| Job dispatch | Cloudflare Queues with retries and a dead-letter queue | Durable generation and benchmark messages |
| Database | Managed PostgreSQL (Neon, Supabase, AWS RDS, or equivalent) | Source of truth; Cloudflare does not replace PostgreSQL here |
| Postgres acceleration | Hyperdrive only after compatibility/performance testing | Optional for Worker-side Postgres access; not required for Python SQLAlchemy |
| Abuse protection | WAF rate-limiting rules and Turnstile | Login, signup, generation, uploads, and public forms |
| Private beta perimeter | Cloudflare Access | Invite-only staging/beta perimeter; not a replacement for product authorization |
| Edge/platform telemetry | Workers Logs and Analytics | Request, error, and performance visibility |

Cloudflare currently recommends its Workers path for full-stack Next.js, R2
offers an S3-compatible API and lifecycle rules, Queues supports retries and
dead-letter queues, and Containers can run existing Linux container images.
References:

- [Next.js on Cloudflare Workers](https://developers.cloudflare.com/workers/framework-guides/web-apps/nextjs/)
- [Cloudflare Containers](https://developers.cloudflare.com/containers/)
- [Cloudflare Queues](https://developers.cloudflare.com/queues/)
- [Cloudflare R2 S3 API](https://developers.cloudflare.com/r2/api/s3/api/)
- [Cloudflare R2 lifecycle setup](https://developers.cloudflare.com/r2/get-started/s3/)
- [Cloudflare Hyperdrive supported databases](https://developers.cloudflare.com/hyperdrive/reference/supported-databases-and-features/)
- [Cloudflare WAF rate limiting](https://developers.cloudflare.com/waf/rate-limiting-rules/)
- [Cloudflare Turnstile](https://developers.cloudflare.com/turnstile/)
- [Cloudflare Access applications](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/)
- [Workers observability](https://developers.cloudflare.com/workers/observability/)

## 3. Identity, tenancy, and authorization model

### Recommended identity approach

Use a managed identity provider for product accounts rather than building
password storage. Clerk, Auth0, WorkOS, or Supabase Auth are reasonable
candidates. Select one during Week 1 using these required capabilities:

- Email verification, password reset, and optional passwordless login.
- MFA for administrators and organization owners.
- Organizations/teams or reliable custom claims.
- JWT access tokens and a stable JWKS endpoint for FastAPI validation.
- Session revocation and audit events.
- OAuth/OIDC and future enterprise SSO support.
- Data-processing terms suitable for the intended launch regions.

The frontend obtains a short-lived session token. FastAPI validates signature,
issuer, audience, expiry, and required claims server-side. The API builds a
request context containing `user_id`, `organization_id`, `role`, and plan
limits. It never accepts an organization ID from the browser without verifying
membership.

### Roles

| Role | Scope | Purpose |
|---|---|---|
| User | Own organization | Normal creation and analysis workflows |
| Organization admin | Own organization | Members, organization settings, quotas, retention, API tokens |
| Support read-only | Explicit time-limited tenant grant | Diagnose metadata without downloading customer data by default |
| Platform admin | Entire platform | Operations, security, catalog, billing, incidents |

Platform admins should use a separate admin route or hostname, mandatory MFA,
shorter sessions, audit logging, and no ability to silently impersonate a user.
If support impersonation is introduced, require a reason, time limit, visible
banner, immutable audit event, and customer-visible record.

### Authorization checklist

- [ ] Add `organizations`, `memberships`, `roles`, `invitations`,
      `api_tokens`, and `audit_events` tables.
- [ ] Add `owner_user_id` and `organization_id` to runs, jobs, files,
      templates, benchmarks, benchmark runs, evaluations, streams, test
      packages, and saved dashboards.
- [ ] Backfill existing rows into a migration-only seed organization.
- [ ] Enforce tenant filters in repository/service methods, not only UI routes.
- [ ] Reject cross-tenant object IDs with `404` to avoid resource enumeration.
- [ ] Hash API tokens; show the plaintext only once at creation.
- [ ] Add scopes such as `runs:read`, `runs:write`, `artifacts:read`, and
      `benchmarks:write`.
- [ ] Add tests for every protected endpoint: owner allowed, member allowed,
      other tenant denied, suspended user denied, admin audited.
- [ ] Remove browser support for `NEXT_PUBLIC_ERRDAIN_API_KEY` before public
      beta.
- [ ] Require recent authentication/MFA for role changes, token creation, and
      destructive organization actions.

## 4. Admin and user product separation

### Navigation and feature visibility

| Area | User sees | Organization admin sees | Platform admin sees |
|---|---|---|---|
| Home | Onboarding, recent work, quota status | Team onboarding and usage summary | Platform status and launch controls |
| Scenario Library | Published scenarios allowed by plan | Same plus organization favorites | Draft/experimental scenarios, validation readiness, catalog publishing |
| Scenario Builder | Generate within row/concurrency quota | Organization defaults and limits | Global safety limits and feature flags |
| Run History | Own/team runs according to membership | Organization runs and retention controls | Metadata across tenants; content only through audited support access |
| Templates | Own/team templates | Sharing and organization defaults | Global starter-template publishing |
| Benchmarks | Own/team benchmarks and detector results | Team governance and usage | Platform health, failed orchestration, abuse investigation |
| Streams | Own authorized streams | Organization stream policy | Global stream health and emergency disable |
| Test Packages | Create, version, execute, export, share within team | Approve shared packages and retention | Publish curated samples, inspect failures, quarantine unsafe packages |
| Dashboards | Personal/team quality, runs, quota, trends | Organization adoption, costs, members, retention | Tenants, reliability, queues, storage, security, support and business KPIs |
| Settings | Profile, notification, personal tokens | Members, roles, organization, billing, retention | Plans, limits, feature flags, providers, incident settings |
| Admin | Hidden and route-denied | Organization administration only | Dedicated platform-admin console |

### Test Packages — minimum functional release

A test package is a versioned, reproducible contract containing scenarios,
generation settings, assertions, expected evidence, and output artifacts.

- [ ] Package model: name, description, owner, organization, semantic version,
      status, tags, scenario versions, seed policy, and timestamps.
- [ ] Package contents: one or more scenarios, row counts, output formats,
      failure plans, validators, quality thresholds, and expected outcomes.
- [ ] Lifecycle: draft → validated → published → deprecated/archived.
- [ ] Actions: create, clone, edit draft, validate, publish version, run,
      compare, download manifest/ZIP, archive.
- [ ] Reproducibility: immutable published versions, catalog version, generator
      version, seed, checksum, and environment metadata.
- [ ] Permissions: private, organization-shared, and admin-curated; no public
      sharing in private beta.
- [ ] CI usage: scoped service token, non-interactive run endpoint, job polling,
      machine-readable result, stable exit/result contract.
- [ ] Safety: package size limits, upload type validation, malware scanning if
      arbitrary files are later accepted, and signed downloads.
- [ ] Admin view: failed packages, heavy packages, version usage, quarantine,
      curated library, and compatibility alerts.

### Dashboards — minimum functional release

User dashboard:

- [ ] Runs completed/failed, success rate, duration, and generated rows.
- [ ] Quality score trend and issues detected by domain/scenario.
- [ ] Artifact storage and retention dates.
- [ ] Remaining monthly rows, concurrent jobs, storage, and API quota.
- [ ] Recent failures with a direct route to actionable evidence.
- [ ] Test-package pass/fail trend and latest version usage.
- [ ] CSV export for the user's organization.

Organization-admin dashboard:

- [ ] Active members, usage by member/project, quota consumption, and costs.
- [ ] Shared test-package adoption and failure trends.
- [ ] API-token last-used data and stale-token warnings.
- [ ] Retention/deletion status and audit events.

Platform-admin dashboard:

- [ ] Active organizations/users and activation/retention funnel.
- [ ] API latency/error rate, generation duration, queue depth/age, retries,
      dead-letter messages, worker saturation, and failure categories.
- [ ] PostgreSQL connections/storage/slow queries and backup status.
- [ ] R2 storage, object count, download volume, lifecycle failures, and cost.
- [ ] Per-tenant usage anomalies, rate-limit events, auth failures, and blocked
      requests.
- [ ] Release version, migrations, feature flags, incident banner, and provider
      status.
- [ ] Support queue, known issues, and beta feedback summaries.

Do not expose platform-wide admin analytics from the existing `/admin` route
until server authorization and route-level UI guards are complete.

## 5. Durable jobs, storage, and database

### Durable generation jobs

Recommended contract:

1. API authenticates the request, checks quota, and creates a database job in
   one transaction.
2. API publishes the job ID and organization ID to Cloudflare Queues.
3. A Python worker claims the job using an idempotency key.
4. Worker writes heartbeats and progress, generates into temporary local disk,
   uploads final artifacts to R2, and commits the manifest.
5. Worker marks completion only after storage and database reconciliation.
6. Retryable failures use bounded exponential backoff; terminal failures move
   to a dead-letter queue and alert operations.

- [ ] Define job states: queued, claimed, running, uploading, validating,
      completed, cancelling, cancelled, retrying, failed, dead-lettered.
- [ ] Add attempt count, worker ID, heartbeat, lease expiry, idempotency key,
      cancellation timestamp, and structured error fields.
- [ ] Make retries safe; never create duplicate billable runs/artifacts.
- [ ] Requeue abandoned leases after worker death.
- [ ] Cap concurrency by plan and organization.
- [ ] Add queue-depth, oldest-message, retry, DLQ, and duration alerts.
- [ ] Add integration tests that terminate a worker mid-job and confirm recovery.

### R2 artifact storage

- [ ] Create separate private `errdain-staging` and `errdain-production`
      buckets.
- [ ] Use bucket-scoped read/write credentials only from backend/worker secrets.
- [ ] Set `STORAGE_BACKEND=s3-compatible`, R2 endpoint, region `auto`, and
      private bucket name.
- [ ] Use keys such as `organizations/{org_id}/runs/{run_id}/...`.
- [ ] Store checksums, content type, size, generator version, and expiry in
      PostgreSQL.
- [ ] Generate short-lived signed download URLs after authorization.
- [ ] Set lifecycle deletion by product plan; suggested beta default is 7 days
      for generated datasets and 30 days for reports/ground truth.
- [ ] Test upload, download, expiry, unauthorized access, lifecycle deletion,
      and orphan cleanup.
- [ ] Never enable an R2 public development URL for customer artifacts.

### Managed PostgreSQL

- [ ] Select a managed provider and region close to the backend workers.
- [ ] Require TLS certificate verification.
- [ ] Create different app, migration, read-only support, and backup roles.
- [ ] Enable automated backups and point-in-time recovery where available.
- [ ] Define connection-pool limits and alerts before load testing.
- [ ] Run Alembic as one release step, never concurrently from every replica.
- [ ] Test forward migration, rollback/roll-forward strategy, and restoration
      into an isolated database.
- [ ] Set recovery objectives for beta: RPO ≤ 24 hours, RTO ≤ 4 hours; improve
      before paid enterprise commitments.
- [ ] Schedule quarterly restore tests after launch.

## 6. Security and production hardening

### Secrets and environments

- [ ] Create separate Cloudflare projects/accounts or strictly separated
      environments for preview, staging, and production.
- [ ] Store identity, database, R2, webhook, email, and error-tracking secrets
      in platform secret stores; never in Git or `NEXT_PUBLIC_*` variables.
- [ ] Rotate all development/example credentials before staging.
- [ ] Use random production database credentials; never deploy `errdain123`.
- [ ] Restrict CORS to exact `https://app.errdain.com` and required preview
      origins; never use `*` with credentials.
- [ ] Disable query-string stream tokens in production.
- [ ] Allowlist webhook destinations and keep SSRF protections tested.
- [ ] Establish a 90-day rotation policy and immediate incident rotation runbook.

### Edge and application controls

- [ ] Put `app.errdain.com` and `api.errdain.com` behind Cloudflare proxying.
- [ ] Enable TLS Full (strict), automatic HTTPS redirects, and HSTS only after
      every required subdomain supports HTTPS.
- [ ] Add CSP, `frame-ancestors`, content-type, referrer, and permissions
      policies; test sign-in and downloads after CSP enforcement.
- [ ] Add Turnstile to signup, waitlist, password-reset abuse paths, and any
      anonymous expensive operation.
- [ ] Add Cloudflare rate limits for login, generation, uploads, and API bursts.
- [ ] Add Redis/shared application quotas if multiple API or worker instances
      must enforce exact per-user limits.
- [ ] Validate content type, extension, payload structure, and size on detector
      uploads; scan arbitrary uploads before future expansion.
- [ ] Use constant-time token comparison and hashed/revocable API tokens.
- [ ] Log authorization decisions and administrative changes without logging
      tokens, credentials, or dataset contents.
- [ ] Add dependency, secret, container-image, and static-code scanning to CI.
- [ ] Add a security disclosure address such as `security@errdain.com` and a
      `security.txt` file.

### pgAdmin

- [ ] Keep pgAdmin out of production Compose/manifests.
- [ ] Do not publish port 5051 on staging or production.
- [ ] Use provider consoles through MFA/VPN/Access for emergency administration.
- [ ] Use a read-only database role for normal support investigation.

## 7. Observability, support, and operations

- [ ] Error tracking: Sentry or equivalent for frontend, API, and workers with
      release/environment tags and source maps.
- [ ] Structured logs: request ID, job ID, run ID, organization ID, service,
      version, duration, and result; redact sensitive fields.
- [ ] Metrics: request rate/error/latency, auth failures, queue depth/age,
      generation duration/failure, CPU/memory/disk, DB health, R2 errors, and
      quota denials.
- [ ] Uptime: probe `/health`, `/ready`, login, scenario catalog, and a synthetic
      small generation flow from outside the platform.
- [ ] Alerts: paging for total outage/data risk/security; ticket/chat for rising
      error rate, capacity, DLQ, storage, or cost.
- [ ] Status page: `status.errdain.com` with frontend, API, generation, storage,
      and downloads.
- [ ] Runbooks: rollback, DB restore, queue drain, stuck job, leaked token,
      provider outage, abusive tenant, artifact deletion, and incident notice.
- [ ] Support: `support@errdain.com`, response target, triage labels, escalation
      owner, and known-issues page.
- [ ] Audit: login, membership/role change, API token events, downloads,
      destructive actions, admin access, retention deletion, and policy change.

## 8. Legal, privacy, retention, and trust

Obtain qualified legal review before live launch; this checklist is product
preparation, not legal advice.

- [ ] Privacy Policy: collected account, usage, security, support, and telemetry
      data; purposes; subprocessors; retention; rights; contact.
- [ ] Terms of Service: acceptable use, ownership, generated data, availability,
      limitations, termination, and governing terms.
- [ ] Acceptable Use Policy: no unlawful, harmful, credential, regulated-person,
      or re-identification datasets; no platform abuse.
- [ ] Data Retention Policy: database metadata, artifacts, backups, logs,
      analytics, support records, and deletion windows.
- [ ] Cookie/analytics disclosure and consent behavior where legally required.
- [ ] Data Processing Addendum and subprocessor list before business customers.
- [ ] Account and organization deletion workflow, including artifact deletion
      and backup-expiry explanation.
- [ ] Data export workflow for customer-owned metadata.
- [ ] Known Issues, support policy, security disclosure, and service status.
- [ ] Marketing review: do not claim enterprise-grade, compliant, anonymous, or
      production-safe behavior without evidence.

## 9. Ordered timeline and deadlines

### Week 1 — architecture and launch controls

Dates: September 8–11, 2026  
Exit deadline: September 11

- [ ] Name engineering, product, security, operations, and legal owners.
- [ ] Freeze beta scope and hide unfinished claims/features behind flags.
- [ ] Choose identity provider, managed PostgreSQL, error tracking, email, and
      backend deployment primary/fallback.
- [ ] Create a threat model and data-flow diagram.
- [ ] Define roles, organization boundaries, quotas, retention, RPO, and RTO.
- [ ] Create preview/staging/production environment inventory and budget alerts.
- [ ] Convert this plan into tracked issues with owners and acceptance criteria.

Deliverable: approved architecture decision record and launch board.

### Weeks 2–3 — authentication and tenant isolation

Dates: September 14–25  
Exit deadline: September 25

- [ ] Integrate login, verification, reset, logout, and session expiry.
- [ ] Add organizations, memberships, invitations, and four-role model.
- [ ] Add tenant ownership columns and migrations to every protected resource.
- [ ] Enforce server-side authorization and admin route separation.
- [ ] Replace shared browser API key with short-lived user tokens.
- [ ] Add tenant-isolation and privilege-escalation tests.
- [ ] Require MFA for platform admins and organization admins.

Deliverable: two test organizations cannot discover or access each other's data.

### Weeks 4–5 — durable infrastructure and Cloudflare staging

Dates: September 28–October 9  
Exit deadline: October 9

- [ ] Deploy Next.js staging frontend to Cloudflare Workers.
- [ ] Configure `staging.errdain.com`/`api-staging.errdain.com`, TLS, DNS, and
      strict CORS.
- [ ] Deploy managed PostgreSQL and perform migration/restore test.
- [ ] Create private staging R2 bucket, signed downloads, and lifecycle rules.
- [ ] Replace in-process background tasks with Queues plus durable workers.
- [ ] Add retry, idempotency, cancellation, heartbeat, lease, and DLQ behavior.
- [ ] Pilot FastAPI/generator image in Cloudflare Containers.
- [ ] Run 100 concurrent small jobs and 10 maximum-beta jobs; record cold start,
      duration, memory, CPU, failures, and cost.
- [ ] Select fallback container host by October 7 if the Containers gate fails.

Cloudflare Containers gate: p95 small-job start under 30 seconds, no job loss,
no local-disk dependency after completion, stable memory at beta max, and cost
within the approved budget.

Deliverable: restart-resilient staging generation with private durable files.

### Weeks 6–7 — Test Packages and role-specific Dashboards

Dates: October 12–23  
Exit deadline: October 23

- [ ] Implement Test Package schema, draft/version/publish/run/archive flow.
- [ ] Make published versions immutable and reproducible.
- [ ] Add organization sharing and admin-curated starter packages.
- [ ] Implement user, organization-admin, and platform-admin dashboards.
- [ ] Hide platform-admin navigation and enforce API permissions independently.
- [ ] Add quota visibility and direct links from failures to evidence.
- [ ] Add dashboard query indexes, pagination, and date filters.

Deliverable: invited user completes package creation → run → evidence → export.

### Week 8 — hardening, observability, and legal staging

Dates: October 26–30  
Exit deadline: October 30

- [ ] Configure WAF, rate limits, Turnstile, CSP, HSTS readiness, and secrets.
- [ ] Add Sentry/error tracking, structured logs, metrics, uptime, and alerts.
- [ ] Remove pgAdmin and development credentials from deploy definitions.
- [ ] Add backup, rollback, token leak, queue recovery, and deletion runbooks.
- [ ] Complete dependency/container/secret scans and external security review.
- [ ] Publish draft privacy, terms, AUP, retention, support, and known issues.
- [ ] Run accessibility, responsive, browser, and download testing.

Deliverable: release candidate with zero open critical/high security findings.

### Week 9 — launch rehearsal

Dates: November 2–6  
Exit deadline: November 6

- [ ] Run full CI/CD deployment from a signed release candidate.
- [ ] Run backup restore and worker-kill recovery drills.
- [ ] Run load/cost tests at twice expected private-beta traffic.
- [ ] Execute complete user/admin permission matrix.
- [ ] Seed curated scenarios and 5–10 starter test packages.
- [ ] Complete quick start, tester missions, demo video, support channel, and
      feedback/bug forms.
- [ ] Conduct go/no-go review and record accepted risks.

Deliverable: `v1.0.0-beta.1` and signed private-beta approval.

### Private beta — 15–25 invited users

Dates: November 9–27  
Entry deadline: November 9

- [ ] Start with 5 users, then 15, then 25 after 48-hour health checks.
- [ ] Review errors, queue/DLQ, cost, storage, auth, and feedback daily.
- [ ] Hold twice-weekly bug triage; ship only blocker/high-value corrections.
- [ ] Measure activation, first successful generation, package completion,
      repeat use, failure rate, support burden, and value/willingness-to-pay.
- [ ] Complete at least one account deletion and artifact-retention test.

Exit gate: ≥80% invited-user activation, ≥70% first-generation completion,
≥50% tester mission completion, <2% platform-caused job failure, no tenant data
leak, no unresolved critical/high security defect, and acceptable unit cost.

### Public-beta preparation and launch

Dates: November 30–December 11  
Public-beta target: December 7

- [ ] Close private-beta P0/P1 defects and document accepted P2 issues.
- [ ] Enable self-service signup with email verification and Turnstile.
- [ ] Add automated quotas, abuse suspension, support SLA, and status page.
- [ ] Publish final beta legal/trust pages and subprocessor list.
- [ ] Run external penetration test or focused independent security review.
- [ ] Add billing only after quota and entitlement tests pass.
- [ ] Release gradually: 10%, 25%, 50%, 100% with rollback thresholds.

Exit gate: two stable weeks, restore drill passed, no P0/P1 issues, support
capacity demonstrated, monitoring coverage complete, and cost forecast approved.

### Live-launch hardening and release

Dates: December 14, 2026–January 12, 2027  
Code freeze: December 18  
Final rehearsal: January 5–8  
Live launch: January 12

- [ ] Review public-beta cohorts, retention, failures, latency, and unit costs.
- [ ] Close live-launch P0/P1 issues and publish remaining known issues.
- [ ] Confirm billing/refunds/tax handling if paid plans are enabled.
- [ ] Repeat restore, rollback, incident communication, and compromised-key
      drills.
- [ ] Confirm on-call ownership and provider escalation paths.
- [ ] Tag signed release, retain rollback image, and deploy progressively.
- [ ] Monitor launch continuously for the first 24 hours and daily for 14 days.

## 10. People and resource plan

Minimum practical staffing through launch:

| Capacity | Recommended allocation | Main responsibility |
|---|---:|---|
| Technical/product founder | 1.0 FTE | Architecture, backend, product decisions, launch ownership |
| Frontend/full-stack engineer | 0.5–1.0 FTE | Auth UI, role-specific product, Test Packages, Dashboards |
| Platform/DevOps engineer | 0.25–0.5 FTE | Cloudflare, queues/workers, CI/CD, DB, observability, incident readiness |
| Product designer/research | 0.2 FTE | Onboarding, missions, usability, dashboards, feedback synthesis |
| Security reviewer | 3–5 focused days | Threat model, auth/tenancy review, upload/SSRF review, launch retest |
| Legal/privacy counsel | 3–5 focused days | Terms, privacy, retention, AUP, DPA/subprocessors |
| Beta support/operations | 5–10 hours/week | Tester onboarding, triage, known issues, communications |

If one person is doing all engineering, keep the January 12 live date but reduce
beta scope to 20–30 curated scenarios, CSV/JSON first, one organization per
user, and only the essential Test Package/Dashboard capabilities. Do not remove
tenant isolation, durable jobs, private storage, backups, or monitoring to save
time.

### Initial service budget categories

- Cloudflare Workers Paid plan and usage.
- Cloudflare Containers usage or fallback container host.
- R2 storage and operations.
- Managed PostgreSQL with backups/PITR.
- Queue/worker usage; optional Redis if exact shared quotas/Celery are used.
- Identity provider monthly active users.
- Error tracking/log retention and uptime/status monitoring.
- Transactional email.
- Security review and legal review.
- Domain/email/support tooling.

Set alerts at 50%, 75%, 90%, and 100% of the approved monthly beta budget.
Cloudflare Workers Paid currently starts with a minimum monthly charge and R2
is usage based; verify prices again immediately before purchasing or launch:

- [Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/)
- [R2 pricing](https://developers.cloudflare.com/r2/pricing/)

## 11. Launch scorecard

Review weekly. A red launch gate blocks promotion to the next environment.

| Area | Beta gate | Live gate |
|---|---|---|
| CI/CD | All tests, audits, build, migrations green | Same plus signed/tagged rollback release |
| Security | Zero critical/high; tenant tests pass | Independent review closed; incident drills pass |
| Reliability | <2% platform job failure | <1% and two stable weeks |
| Performance | p95 normal API <500 ms excluding jobs | Capacity test at 2× forecast |
| Jobs | Restart recovery and DLQ proven | Alert/runbook and replay proven |
| Database | Automated backup and restore test | PITR/restore and RPO/RTO approved |
| Storage | Private signed access and lifecycle | Orphan cleanup and deletion audit proven |
| Product | Core mission completed without help by ≥50% | Activation/retention targets approved |
| Support | Owner and known issues available | Response targets and escalation demonstrated |
| Legal | Beta terms/privacy/retention published | Final terms, privacy, AUP, subprocessors published |
| Cost | Hard quotas and budget alerts | Unit economics and scale forecast approved |

## 12. Immediate next 10 actions

1. Approve the November 9 private-beta and January 12 live-launch targets.
2. Choose the identity provider and managed PostgreSQL provider.
3. Decide whether Cloudflare Containers is the primary backend pilot or whether
   the existing Render blueprint remains primary behind Cloudflare.
4. Create the organization/role/ownership schema and migration design.
5. Create staging Cloudflare Workers, R2, Queues, DNS, and secret environments.
6. Refactor generation from FastAPI `BackgroundTasks` into the durable job
   contract.
7. Write the Test Package product/API specification and acceptance tests.
8. Write the three Dashboard specifications and permission matrix tests.
9. Contract security and legal reviews for the October 26–30 window.
10. Turn every checklist item into an issue with owner, estimate, dependency,
    evidence link, and status.

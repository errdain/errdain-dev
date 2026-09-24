# Errdain Product Roadmap

Updated: 2026-09-24

## Product direction

Errdain should become the benchmark and test-data workspace for data-quality
teams: select or configure a realistic failure scenario, generate reproducible
data and ground truth, run a detector, and compare its precision, recall, and
operational behavior over time.

The immediate objective is not catalog size. It is proving that this loop is
understandable, trustworthy, repeatable, and valuable to a small group of real
users.

## Current baseline

The repository already includes:

- Dataset generation across multiple enterprise domains and load modes.
- Failure injection, ground truth, validation, evidence, and quality scoring.
- Scenario Library and Builder, saved templates, run history, and comparison.
- Benchmark definitions, detector-result ingestion, and precision/recall/F1.
- Batch and stream APIs, file previews/downloads, object-storage support, and
  retention tooling.
- FastAPI, PostgreSQL/Alembic, Next.js, Docker assets, and deployment guidance.
- A documented staging result of 378 backend tests, 72 browser checks, clean
  dependency audits, and no critical or serious accessibility findings.

Known product and platform gaps:

- JWT/JWKS user identity and server-side role enforcement are implemented;
  tenant-scoped resource authorization remains the next security gate.
- Resources do not yet have production-grade per-user or per-organization
  ownership enforcement.
- Generation and benchmark work is process-local and cannot recover reliably
  after a restart.
- Rate limits are process-local.
- Product analytics, error monitoring, support operations, and beta feedback
  loops are not yet established.
- Only a small subset of the 760 catalog scenarios is executable; catalog count
  must not be confused with runnable product depth.
- Dashboards and Test Packages remain unfinished product surfaces.
- Remaining moderate accessibility/semantic issues should be fixed.

## Product principles

1. **Trust before breadth.** Reproducibility and correct ground truth matter
   more than adding domains or scenario cards.
2. **One golden workflow.** Optimize scenario to dataset to detector to score to
   comparison before introducing adjacent workflows.
3. **Never overstate readiness.** Clearly label executable, custom-reference,
   specification-only, experimental, and restricted capabilities.
4. **Measure behavior.** Roadmap promotion depends on activation, completion,
   retention, correctness, and buying signals—not feature count.
5. **Expand through reusable capabilities.** Add primitives, validators, tables,
   and columns that unlock groups of scenarios rather than isolated demos.

## Roadmap overview

| Phase | Target window | Outcome | Exit gate |
|---|---|---|---|
| 0. Baseline and freeze | Week 0–1 | One releasable beta build | Repeatable release candidate and resolved scope |
| 1. Controlled beta | Weeks 2–5 | Validate comprehension and value | Core completion >=80%, no critical bugs |
| 2. Public-beta foundation | Weeks 6–10 | Safe multi-user product | Identity, ownership, durable jobs, observability |
| 3. Workflow depth | Weeks 11–16 | Repeatable team benchmarking | Test Packages, useful dashboards, scheduled/regression runs |
| 4. Capability expansion | Months 5–7 | Materially larger executable library | Expansion driven by usage and leverage data |
| 5. Enterprise readiness | Months 8–12 | Pilots with organizational controls | SSO/RBAC/auditability/SLOs validated with design partners |

## Phase 0 — Baseline and freeze (Week 0–1)

Goal: produce a single, trustworthy beta baseline and remove ambiguity between
the application, the marketing site, and experimental catalog work.

### Product and scope

- Define the primary persona: data-quality engineer or QA/data-platform engineer
  evaluating rule-based or ML-based detectors.
- Define the golden path: sign in -> choose featured scenario -> configure ->
  generate -> inspect ground truth -> submit detector output -> review score ->
  compare/re-run.
- Select 20–30 featured scenarios across 3–4 strongest domains.
- Label all scenarios by execution status and hide specification-only scenarios
  from the default beta experience.
- Write the beta promise and explicit non-goals.

### Engineering

- Re-run the backend, typecheck/build, migration, and browser regression gates
  from a clean checkout and record the result against a release commit.
- Resolve or intentionally split the current uncommitted work before tagging.
- Fix duplicate/nested main landmarks, missing H1s, and the unexplained static
  resource 404.
- Add a checked-in smoke test for the golden path rather than relying only on a
  temporary validation harness.
- Verify secret handling and remove environment files from release artifacts.
- Confirm backup, restore, retention, and generated-file cleanup procedures.

### Launch operations

- Create a quick-start guide, 5–10 minute walkthrough, tester mission pack,
  feedback form, bug template, known-issues page, and support channel.
- Seed example scenario and benchmark runs so a new user sees value immediately.
- Define severity, response owner, and response-time expectations for beta bugs.

### Exit criteria

- A tagged `v1.0.0-beta` candidate deploys from a clean checkout.
- Golden-path smoke passes in the beta environment.
- Zero open critical/high correctness or security findings.
- Every exposed capability is either verified or visibly marked experimental.

## Phase 1 — Controlled beta (Weeks 2–5)

Goal: determine whether target users understand the workflow, complete it, come
back, and care enough to evaluate the product at work.

### Week 2: instrument and onboard

- Add privacy-conscious events for sign-in, scenario selection, generation,
  evidence views, benchmark creation, detector submission, comparison, download,
  abandonment, and errors.
- Add client and server error monitoring with release/environment tags.
- Invite 5–10 technical users and give each a structured mission.
- Conduct at least five observed onboarding sessions.

### Week 3: remove workflow friction

- Fix blockers within 24–48 hours; batch medium and low issues weekly.
- Improve empty, loading, timeout, retry, cancellation, and failure states.
- Add contextual explanations for ground truth, evidence, precision, recall, F1,
  and PASS/FAIL thresholds.
- Add sample detector-output files and copyable contract examples.
- Track time-to-first-success and assistance required.

### Week 4: test repeat use and willingness to pay

- Invite enough additional users to reach 10–15 total participants.
- Ask users to save a template, return, rerun it, and compare results.
- Interview at least five users about current alternatives, urgency, team size,
  security needs, and budget ownership.
- Test two or three packaging hypotheses without building billing yet.

### Week 5: decision gate

- Consolidate behavior data, interviews, defects, and requested capabilities.
- Choose one result: proceed to public-beta hardening, run a focused patch cycle,
  or narrow/reposition the product.

### Exit criteria

- At least 80% complete the golden path without live assistance.
- At least 70% complete one benchmark.
- At least 50% of activated users return during the beta.
- No critical bugs and fewer than three unresolved high bugs.
- At least three users are willing to evaluate Errdain in a work context.
- The next phase is prioritized from observed evidence.

## Phase 2 — Public-beta foundation (Weeks 6–10)

Goal: replace controlled-demo assumptions with safe, observable, recoverable
multi-user operation.

### Identity and authorization (P0)

- Add real authentication with server-validated sessions or tokens.
- Add `owner_id`/`organization_id` to runs, jobs, templates, benchmarks,
  evaluations, files, streams, and analytics-relevant records.
- Enforce ownership in every read, list, mutate, download, preview, stream, and
  admin endpoint.
- Add migrations, backfill policy, authorization tests, and an admin role.
- Remove the browser-exposed demo API-key path from public deployments.

### Durable execution (P0)

- Move generation and benchmark orchestration to a durable queue and workers.
- Make jobs idempotent; support retry with backoff, cancellation, lease/heartbeat,
  timeout, and recovery of abandoned work.
- Persist step-level progress and stable failure codes.
- Enforce per-user and per-organization concurrency and quotas.

### Storage and lifecycle (P0)

- Use object storage by default outside development.
- Use short-lived signed downloads and tenant-scoped object keys.
- Automate retention and expose retention status to users.
- Validate backup/restore and deletion behavior, including metadata cleanup.

### Reliability, security, and operations (P0)

- Move rate limiting and shared ephemeral state to Redis/edge infrastructure.
- Add structured logs, request/job correlation IDs, metrics, traces, and alerts.
- Define service indicators for API availability, queue latency, job success,
  generation duration, and artifact availability.
- Add dependency, secret, container, and upload security checks to CI.
- Threat-model uploads, signed downloads, webhook delivery, streaming tokens,
  SSRF controls, authorization boundaries, and admin APIs.
- Create incident, rollback, database migration, and data-recovery runbooks.

### Product readiness (P1)

- Add onboarding checklist, sample project, documentation center, status/error
  communication, and in-product feedback.
- Make usage and plan limits visible before a user starts expensive work.
- Add email/in-app notification for long-running job completion or failure.

### Exit criteria

- Cross-tenant access tests cover every protected resource and pass.
- Jobs recover from worker/API restarts without duplicate artifacts.
- Load test passes at the agreed beta concurrency and dataset sizes.
- Error monitoring and operational alerts are exercised in a game day.
- Backup and restore are proven, not merely documented.
- Public-beta privacy, terms, acceptable-use, and retention policies are ready.

## Phase 3 — Workflow depth (Weeks 11–16)

Goal: make Errdain a repeatable team workflow rather than a one-off generator.

### Test Packages

- Group scenarios, generation settings, detector contracts, scoring thresholds,
  and expected artifacts into versioned packages.
- Support draft, published, archived, duplicate, export, and import states.
- Run a package manually and expose per-scenario and aggregate results.
- Pin seeds, generator version, schema version, and scenario version so results
  remain reproducible.

### Dashboards

- Replace the placeholder with benchmark trends, recent failures, run duration,
  quality-score distribution, scenario coverage, and regression indicators.
- Provide filters by project/package, domain, detector version, date, and status.
- Link every aggregate to the underlying run and evidence.

### Detector integration

- Add service/API execution in addition to result-file upload.
- Define request/response schema, authentication, timeout, retry, and isolation.
- Store detector name and version and make comparisons version-aware.
- Provide a minimal SDK or CI example for submitting results.

### Regression and collaboration

- Add baseline runs and configurable regression thresholds.
- Add scheduled package runs and webhook/CI status output.
- Add comments/notes, shareable internal links, ownership transfer, and basic
  project/team organization.

### Exit criteria

- A team can create a versioned package, run it against a detector, identify a
  regression, inspect evidence, and reproduce the result.
- At least 30% of active beta teams use a saved package more than once.
- Dashboard aggregates reconcile exactly with underlying runs.

## Phase 4 — Capability expansion (Months 5–7)

Goal: increase executable coverage where it creates customer value and platform
leverage.

### Expansion order

1. Implement reusable validator gaps with highest catalog leverage: SLA,
   aggregate balance, cross-table consistency, state transition, threshold, and
   temporal order.
2. Implement reusable mutation gaps: aggregate mismatch, cross-table mismatch,
   timestamp delay/out-of-order, sequence gap, invalid state transition,
   calculation error, capacity exceeded, and volume spike.
3. Add tables and columns only where design-partner demand and unlock count
   justify the data-model cost.
4. Promote scenarios in cohorts only after correctness, evidence, performance,
   and UX gates pass.

### Promotion contract

Every promoted scenario must have:

- Deterministic seeded generation.
- Explicit schema/table/column requirements.
- Config validation and bounded parameters.
- Mutation assertions and independent validator assertions.
- Ground truth and evidence reconciliation.
- Performance target at 1K, 10K, and the supported maximum.
- UI discoverability, documentation, and a representative example.

### Exit criteria

- Executable coverage grows by capability cohort, not by re-labeling specs.
- Each expansion cohort has measured usage by at least one design partner.
- No material regression in generation correctness or benchmark latency.

## Phase 5 — Enterprise readiness (Months 8–12)

Goal: satisfy real procurement, governance, and operational requirements for
design-partner pilots.

- Organizations, invitations, RBAC, project isolation, and admin controls.
- SSO/SAML/OIDC and optional directory provisioning based on customer demand.
- Immutable audit log for authentication, configuration, execution, download,
  sharing, deletion, and admin events.
- Encryption/key management, regional/data-residency choices, retention and
  deletion controls, and vendor/security documentation.
- Usage metering, plans, quotas, billing, and entitlement enforcement.
- API versioning, SDKs, service accounts, webhooks, and CI integrations.
- Worker autoscaling, queue isolation, capacity planning, and published SLOs.
- Data warehouse, Kafka-compatible, and cloud-storage connectors selected from
  design-partner workflows—not a broad connector checklist.

Enterprise GA gate:

- Two or more successful design-partner pilots.
- Security and reliability controls validated against an agreed customer
  checklist.
- Measured SLOs meet targets for at least 30 consecutive days.
- Support, incident, backup, recovery, deletion, and access-review processes are
  operational.

## Prioritized backlog

### P0 — before public beta

- Real authentication and full ownership enforcement.
- Durable queue/worker execution and restart recovery.
- Object storage plus automated retention.
- Shared rate limiting/quotas.
- Product analytics, error monitoring, and operational alerting.
- Checked-in golden-path E2E and CI release gates.
- Accessibility landmarks/headings and static 404 cleanup.

### P1 — after the beta signal is positive

- Test Packages.
- Dashboard MVP.
- Detector service/API execution.
- Versioned baselines and regression reporting.
- Scheduled runs, CI status, and completion notifications.
- Team/project organization.

### P2 — evidence-driven expansion

- Additional reusable primitives and validators.
- High-leverage tables/columns and scenario cohorts.
- More connectors and streaming depth.
- Billing, SSO, advanced RBAC, audit export, and compliance work.

### Explicitly defer

- Exposing all 760 catalog scenarios as if executable.
- Building many new domains before current workflows show repeat use.
- Polishing Dashboards before analytics definitions and tenant ownership exist.
- Broad marketplace/connector work without design-partner demand.
- Microservices decomposition before worker and scaling boundaries require it.

## Metrics framework

### North-star metric

**Weekly successful benchmark loops:** unique project/package + detector-version
combinations that complete generation, detector submission/execution, scoring,
and evidence review in a week.

### Funnel

- Invite/sign-up -> first scenario started.
- Scenario started -> dataset generated.
- Dataset generated -> ground truth/evidence viewed.
- Dataset generated -> detector output submitted.
- Detector submitted -> score reviewed.
- Score reviewed -> saved/rerun/compared within 14 days.

### Quality and reliability

- Ground-truth reconciliation error rate.
- Generation and benchmark success rate.
- P50/P95 queue wait and run duration by row count.
- Crash-free sessions and API 5xx rate.
- Artifact download success and worker recovery success.

### Business signal

- Weekly active evaluators and teams.
- Repeat benchmark rate and package reuse.
- Users willing to evaluate at work.
- Design partners started and converted.
- Time saved or detector regressions found, documented per user/team.

## Operating cadence

- Weekly: product funnel, reliability, open critical/high bugs, and top feedback.
- Biweekly: ship/no-ship review and roadmap adjustments.
- Monthly: scenario capability promotion and infrastructure capacity review.
- Quarterly: positioning, packaging, design-partner evidence, and enterprise-gap
  review.

Each roadmap item should have an owner, target metric, release gate, and user
evidence. Work that cannot name those four things stays in discovery.

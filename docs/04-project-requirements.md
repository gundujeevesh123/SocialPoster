# Phase 4 — Project Requirements

Convention: FR = functional, NFR = non-functional. MoSCoW priority in brackets. [M]=Must, [S]=Should, [C]=Could.

## Frontend
- FR-F1 [M] Screens: Login/Register, Connect Accounts, Create Post, Per-Platform Preview, Publish Confirmation, Live Status, Post History, Scheduled Calendar, Settings, Notification Center.
- FR-F2 [M] Drag-and-drop upload with progress, direct-to-bucket presigned PUT, client-side size/type pre-check.
- FR-F3 [M] Per-platform preview cards with live character counts and validation warnings before publish.
- FR-F4 [M] Live status via SSE with automatic reconnect; graceful fallback to polling.
- FR-F5 [M] Explicit confirmation modal before any publish; schedule picker with timezone display.
- FR-F6 [S] AI caption generation button with editable results; regenerate per platform.
- FR-F7 [S] Empty/loading/error states for every screen; optimistic UI only where reversible.
- NFR-F1 [M] No platform tokens, secrets, or raw API responses ever reach the browser for non-admin users.
- NFR-F2 [S] Lighthouse ≥ 90 performance/accessibility on dashboard; responsive down to 375px.

## Backend
- FR-B1 [M] REST API v1 (`/api/v1/...`), OpenAPI schema auto-published, JSON errors with stable error codes.
- FR-B2 [M] Endpoints: auth (register/login/logout/verify), media presign+register, drafts CRUD, targets CRUD, publish (idempotent), job status + SSE events, job retry, connected accounts list/disconnect, OAuth start/callback ×3 providers, webhooks (Meta deauth + data deletion), notification prefs, `/healthz` `/readyz`.
- FR-B3 [M] `PlatformPublisher` adapter interface (validate/prepare/publish/verify) with adapters: Facebook, Instagram, LinkedIn, YouTube; mock adapter for dev; registry supports future X/Threads/TikTok/Pinterest.
- FR-B4 [M] Job system: Celery + Redis, `acks_late`, exponential backoff + jitter, max 5 attempts, dead-letter state with notification.
- FR-B5 [M] Scheduler: beat tick each minute; due-post dispatcher using `FOR UPDATE SKIP LOCKED`; overdue-threshold behavior.
- FR-B6 [M] Post/target/job state machines with enforced legal transitions.
- FR-B7 [S] Caption service behind an interface (OpenAI/Anthropic/Gemini swappable); prompt templates per platform; cost cap per workspace/day.
- NFR-B1 [M] p95 API latency < 300 ms (excluding publish, which is async); publish enqueue < 1 s.
- NFR-B2 [M] Idempotent publish path — duplicate requests or retried jobs never double-post.

## Database
- DB-1 [M] PostgreSQL 16; schema per `docs/02-architecture.md` §6 including `workspace_id`, unique constraints, `key_version`, `idempotency_key`, JSONB raw responses, indexes on hot paths.
- DB-2 [M] Migrations via Alembic; every migration reversible and backwards-compatible with running code.
- DB-3 [M] Append-only `audit_logs`; no UPDATE/DELETE grants on it for the app role.
- DB-4 [S] PITR enabled; daily snapshots; quarterly restore drill documented.

## Cloud
- CL-1 [M] Environments: dev, staging, prod — separate DBs, buckets, Redis, OAuth apps, secrets.
- CL-2 [M] Managed Postgres/Redis (no self-hosted DBs at this team size).
- CL-3 [M] All services in one region initially; media bucket with CDN in front for thumbnails.
- CL-4 [S] Infrastructure defined as code (Render blueprint / Terraform) and reviewed like code.

## DevOps
- DO-1 [M] GitHub repo, protected main, PR review required, conventional commits.
- DO-2 [M] CI: lint (ruff, eslint), typecheck (mypy, tsc), tests, **Snyk code scan + SCA (fail on high severity)**, gitleaks secret scan, Docker build.
- DO-3 [M] CD: auto-deploy staging on merge; manual promote to prod; migrations as release phase; instant rollback to previous image.
- DO-4 [S] IaC scanned with Snyk IaC; container image scanned before deploy.
- DO-5 [S] Runbook: on-call basics, common failures (token revoked, quota exhausted, queue backlog), rollback steps.

## Storage
- ST-1 [M] S3-compatible abstraction; R2 default; local MinIO for dev.
- ST-2 [M] Presigned PUT uploads (15-min expiry); presigned GET for platform fetches (24-h expiry, single purpose).
- ST-3 [M] Bucket private by default; no public ACLs; server-side encryption on.
- ST-4 [M] Media pipeline: magic-byte type verification, size caps, EXIF/GPS strip, AV scan, thumbnail, checksum dedupe.
- ST-5 [S] Lifecycle rules: delete orphaned uploads after 7 days; archive published media after 90 days.

## Authentication (app users)
- AU-1 [M] Email + password (Argon2id) with email verification; or managed auth provider — decision recorded as ADR.
- AU-2 [M] Sessions: httpOnly Secure SameSite=Lax cookies; short-lived access + rotating refresh; logout revokes.
- AU-3 [M] Rate-limited login, credential-stuffing lockout, password reset with single-use expiring tokens.
- AU-4 [S] TOTP MFA optional; enforced for workspace owners.
- AU-5 [S] RBAC: owner/editor/viewer roles at workspace level; every query scoped by `workspace_id` (no cross-tenant IDOR).

## OAuth (platform connections)
- OA-1 [M] Authorization Code flow, server-side exchange only, confidential client.
- OA-2 [M] `state` (random, single-use, server-stored) on all flows; PKCE where supported.
- OA-3 [M] Exact-match registered redirect URIs per environment; HTTPS only in staging/prod.
- OA-4 [M] Minimum scopes per platform (see docs/05); scope list stored per connection.
- OA-5 [M] Token lifecycle: proactive refresh where possible, expiry warnings, one-click reconnect, disconnect = local delete + platform revoke call where available.
- OA-6 [M] Meta deauthorize + data deletion callbacks implemented and registered.

## Security
- SE-1 [M] Envelope encryption (AES-256-GCM + KMS) for tokens; `key_version` rotation support.
- SE-2 [M] Secrets only in secret manager / CI secrets; never in code, `.env` not committed; gitleaks enforced.
- SE-3 [M] TLS everywhere; HSTS; secure headers (CSP, X-Frame-Options DENY, nosniff, Referrer-Policy).
- SE-4 [M] Input validation via Pydantic on every endpoint; output encoding; no raw SQL string building.
- SE-5 [M] SSRF defense: workers fetch only your own bucket URLs; any user-supplied URL feature must use an allowlist + no redirects + no private IPs.
- SE-6 [M] Inbound rate limits per user/IP; outbound platform budget trackers.
- SE-7 [M] Logs structured, PII-minimal, token-redacting; no tokens in Sentry breadcrumbs.
- SE-8 [M] Dependency policy: Snyk SCA gate, weekly `snyk monitor`, renovate/dependabot.
- SE-9 [S] Pre-launch: full Snyk suite (code, SCA, IaC, container) clean of high/critical + manual authz review (IDOR hunt) + OAuth flow pen-check.

## Monitoring
- MO-1 [M] Sentry (API, workers, frontend) with release tagging.
- MO-2 [M] Metrics: publish success rate, job latency p95, queue depth, scheduler lag, token refresh failures, per-platform error rates, quota consumption.
- MO-3 [M] Alerts: queue depth > N for 10 min, publish failure rate > 10%/15 min, scheduler lag > 2 min, token refresh failure burst, webhook signature failures.
- MO-4 [S] Uptime checks on `/healthz` + status page.

## Testing
- TE-1 [M] Unit tests: state machines, idempotency logic, encryption round-trip, validators (≥80% on core modules).
- TE-2 [M] Integration: API + DB + Redis via testcontainers; adapter tests against recorded platform responses (VCR-style fixtures).
- TE-3 [M] E2E (Playwright): register → connect (mock provider) → upload → caption → schedule → publish (mock) → status → history.
- TE-4 [M] Contract tests for each platform adapter against sandbox/test accounts before every release that touches them.
- TE-5 [S] Load test: 100 concurrent publishes; chaos test: kill worker mid-publish, assert no duplicate post.

## Documentation
- DC-1 [M] README (setup in ≤10 commands), `.env.example` complete, architecture doc, ADRs for major choices.
- DC-2 [M] Platform playbooks: exact app-setup clicks, scopes, review steps per platform (docs/05 + 06 as living docs).
- DC-3 [S] API reference auto-generated from OpenAPI; onboarding guide for a second developer.

## Deployment
- DP-1 [M] Dockerized API/worker/beat; Next.js on Vercel; Render services for the rest.
- DP-2 [M] Zero-downtime deploys; migrations backwards-compatible; feature flags per platform (`ENABLE_X_REAL`).
- DP-3 [M] Production checklist (docs/11) gate before first real-user launch.

# Phase 9 — Development Roadmap

Complexity: S (≤2 days) · M (3–7 days) · L (1–3 weeks) for one experienced dev with AI tooling. Every milestone ends with its tests green in CI and a Snyk-clean scan (no new high/critical).

**Run two tracks in parallel from day 1:** Track A = code (M0–M10). Track B = platform bureaucracy (Meta Business Verification, LinkedIn product access, Google OAuth verification + audit) — these have weeks of lead time and block only M9/M10, not development, thanks to dev-mode testing.

---

### M0 — Foundations & security rails
- **Objective:** repo + pipeline that makes insecure code hard to merge.
- **Deliverables:** monorepo (`apps/web`, `apps/api`, `packages/shared`), Docker compose (Postgres, Redis, MinIO, mailhog), GitHub Actions (ruff/mypy/eslint/tsc, pytest/vitest, **Snyk code+SCA gate, gitleaks**), `.env.example`, ADR-001 (stack), branch protection.
- **Prereqs:** GitHub repo, Snyk account. **Depends on:** –. **Complexity:** S–M.
- **Testing:** CI runs on a hello-world endpoint + failing-secret canary test (gitleaks catches a planted fake key).
- **Done when:** a PR with a hardcoded secret or vulnerable dep is automatically blocked.

### M1 — Auth, workspaces, DB core
- **Objective:** users can register/login; schema spine exists.
- **Deliverables:** Alembic migrations for full schema (docs/02 §6), Argon2id auth + email verification, sessions (httpOnly), RBAC scaffolding, audit-log writer, rate-limited auth endpoints, security headers middleware.
- **Prereqs:** M0. **Complexity:** M.
- **Testing:** unit (hashing, session rotation), integration (register→verify→login→logout), authz IDOR tests (user A cannot read workspace B), header assertions.
- **Done when:** E2E auth flow passes; audit rows written; OWASP-header scan clean.

### M2 — Media pipeline
- **Objective:** safe upload → validated, platform-ready assets.
- **Deliverables:** presigned PUT flow, magic-byte validation, EXIF strip, AV scan hook, thumbnails, checksums, per-platform validation table (config-driven), signed GET URLs, lifecycle cleanup job.
- **Prereqs:** M1. **Complexity:** M.
- **Testing:** upload matrix (valid/oversize/spoofed-extension/EXIF-laden), signed-URL expiry test, orphan-cleanup test.
- **Done when:** a spoofed `.jpg.exe` is rejected; EXIF GPS provably stripped; platform validation errors surface in API.

### M3 — Drafts, targets, mock publish end-to-end
- **Objective:** the full product loop works with mock adapters — demoable.
- **Deliverables:** drafts/targets CRUD, post state machine, Celery workers + beat, publish endpoint with **Idempotency-Key**, `publish_jobs` with idempotency + retries + backoff, SSE status stream, Live Status + History UI, mock `PlatformPublisher` returning fake URLs.
- **Prereqs:** M1 (M2 for real media). **Complexity:** L. This is the architectural heart.
- **Testing:** state-machine unit tests (illegal transitions), **chaos test: kill worker mid-job → no duplicate**, double-click publish → one job, SSE reconnect, load test 100 concurrent publishes.
- **Done when:** demo: upload → caption → publish → live status → history, all mocked; duplicate-post chaos test green.

### M4 — OAuth connections (all three providers)
- **Objective:** real accounts connect; tokens encrypted at rest.
- **Deliverables:** OAuth start/callback for Meta, LinkedIn, Google with state+PKCE; KMS envelope encryption (`key_version`); account picker (Pages/channel); connected-accounts UI; disconnect + revoke; token-refresh beat job; expiry notifications; Meta deauth + data-deletion webhook endpoints.
- **Prereqs:** M1; dev apps created on each platform (Track B started). **Complexity:** L (three providers × quirks).
- **Testing:** mock-provider integration tests (state mismatch, denied consent, expired code), encryption round-trip + rotation test, webhook signature verification tests, real dev-mode connects for your own accounts.
- **Done when:** your real IG/FB/LinkedIn/YouTube accounts connect on staging; DB dump shows only ciphertext; deauth webhook flips account to `revoked`.

### M5 — First real platform live (Facebook Page or LinkedIn personal)
- **Objective:** one real post published via the full pipeline.
- **Deliverables:** real FacebookPublisher (feed/photo/video) *or* LinkedInPublisher (text/image) behind `ENABLE_*_REAL` flag; error-code mapping (retryable vs permanent); platform budget tracker.
- **Prereqs:** M2–M4. **Complexity:** M.
- **Testing:** contract tests against test Page/profile; forced-failure paths (revoked token mid-publish, rate-limit response) using recorded fixtures.
- **Done when:** scheduled post publishes to the test Page/profile while nobody is logged in, and the permalink appears in History.

### M6 — Remaining platforms
- **Objective:** Instagram container flow, YouTube resumable upload, LinkedIn media, + the platform not chosen in M5.
- **Deliverables:** InstagramPublisher (container→poll→publish, carousel, `content_publishing_limit` check), YouTubePublisher (resumable + progress + quota meter), LinkedIn media upload; per-platform quota UI.
- **Prereqs:** M5 patterns. **Complexity:** L.
- **Testing:** contract tests per adapter on test accounts; container-expiry simulation; resumable-upload interrupt/resume test; quota-exhaustion behavior test.
- **Done when:** one click publishes the same media to all four platforms on test accounts with correct per-platform formatting.

### M7 — Scheduling, timezones, calendar
- **Objective:** future posts fire reliably.
- **Deliverables:** scheduler dispatcher (`FOR UPDATE SKIP LOCKED`), UTC+timezone storage, overdue policy, calendar UI, edit/cancel scheduled posts.
- **Prereqs:** M3. **Complexity:** M.
- **Testing:** DST-boundary cases, restart-during-due-window test (no loss, no dupes), bulk 1k scheduled rows dispatch under 60 s.
- **Done when:** posts scheduled across timezones fire within 60 s of target through worker restarts.

### M8 — Notifications & observability
- **Objective:** humans (user and operator) find out when things break.
- **Deliverables:** notifier worker + in-app center + Resend emails (final-failure, token-expiring, requires-action), Sentry wiring (API/workers/web), metrics + dashboards (publish success rate, queue depth, scheduler lag, quota), alert rules, `/healthz` `/readyz`, runbook v1.
- **Prereqs:** M3/M4. **Complexity:** M.
- **Testing:** alert fire-drill (kill workers → alert within 10 min), email snapshot tests, synthetic failing publish generates user notification.
- **Done when:** on-call can diagnose a failed publish from dashboard + logs alone, without reading code.

### M9 — Security hardening & verification (the user-mandated Snyk gate)
- **Objective:** prove the security policy is enforced in code.
- **Deliverables:** full **Snyk suite run — code, SCA, IaC, container — high/critical = zero**; manual authz review (IDOR hunt across every endpoint); OAuth flow pen-check (state reuse, redirect tampering, token leak via logs); log-redaction audit; dependency freeze + `snyk monitor`; fixes for all findings; security review report committed to `docs/security-reports/`.
- **Prereqs:** M1–M8 code complete. **Complexity:** M.
- **Testing:** the scans *are* the tests; plus regression suite green.
- **Done when:** clean scan report archived; every SE-x requirement in docs/04 maps to a passing check.

### M10 — App reviews & production launch
- **Objective:** external users can use it legally and reliably.
- **Deliverables:** Meta App Review (Advanced Access) submission with screencast + reviewer creds; LinkedIn product approvals; Google OAuth verification + quota/compliance audit submission; production checklist (docs/11) executed; backup restore drill; go-live.
- **Prereqs:** M9; Track B verifications done. **Complexity:** M (elapsed weeks — mostly waiting).
- **Testing:** staging soak (1 week of scheduled posts, zero missed/dup), review-rejection dry run against each platform's checklist.
- **Done when:** a non-team user connects all four platforms and schedules a post that publishes successfully.

---

### Post-launch backlog (ordered)
1. Organization/company posting (LinkedIn org, multi-Page management).
2. New platform adapters: X, Threads (Meta), TikTok, Pinterest — each = adapter + scopes + validation rows (architecture already supports).
3. Analytics ingestion (post performance), best-time-to-post suggestions.
4. Team features: approval workflows, roles per workspace, billing.
5. Mobile companion app (approvals + notifications).

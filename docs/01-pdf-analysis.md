# Phase 1 — PDF Analysis (Critical Review)

Document reviewed: `FounderLabs_Social_Posting_Automation_Guide.pdf` (17 sections).
Reviewer stance: senior architect. Verdict up front: **the PDF is a good MVP build guide (7/10) but it is not a production blueprint.** Its platform flows are directionally correct; its gaps are in authentication, token lifecycle, idempotency, observability, compliance webhooks, and scheduling mechanics — exactly the areas that cause real-world incidents.

---

## 1. Section-by-section review

### §Purpose / One-line idea (p.1)
- **Good:** Official-APIs-only stance stated on page 1. "Work in dev mode first, apply for review later" is the correct sequencing and avoids weeks of blocked time.
- **Missing:** No definition of the *user model* — single brand (FounderLabs only) vs multi-tenant SaaS. This decision changes OAuth app review scope, DB schema (workspaces), and pricing of every downstream choice.
- **Change:** Define target explicitly. Recommendation: build single-workspace first but model the DB as multi-tenant (add `workspace_id` now — trivial today, painful migration later).

### §1 What the application will do
- **Good:** Correct feature cut for an MVP; "store proof" (post IDs, raw API responses) is a mature instinct most guides omit.
- **Missing:** Notifications (required by `context_social.txt`), draft autosave, per-platform *validation feedback* before publish (fail at preview time, not publish time), and a "requires approval" human-in-the-loop state (it appears in §1's status list but nothing in the doc implements it).
- **Production improvement:** Add explicit post lifecycle state machine: `draft → validating → ready → queued → publishing → published | failed | requires_action`. State machines prevent the #1 class of scheduler bugs: illegal transitions on retry.

### §2 Recommended tech stack
- **Good:** Sensible defaults (React, PostgreSQL, Redis queue, object storage, encrypted tokens). Cloudflare R2 mention is smart — Instagram fetches your media, and R2 has zero egress fees.
- **Weak:** "FastAPI **or** NestJS" and "Celery/RQ/BullMQ" hedge across two ecosystems. A build doc must pick one; mixed guidance produces mixed codebases.
- **Weak:** "Cloud secret manager **or** encrypted DB columns" are not equivalent. You need both, layered: secret manager for app credentials, envelope-encrypted DB columns for per-user OAuth tokens (they are data, not config).
- **Change:** Fix the stack: **Next.js frontend, FastAPI + Celery backend, PostgreSQL, Redis, S3-compatible storage (R2), KMS-based envelope encryption.** Justification in `docs/07-technology-comparison.md`.

### §3 High-level architecture
- **Good:** The 7-step flow (upload → draft → OAuth → job per platform → worker → live status → log everything) is the right shape. Job-per-platform is the correct unit of retry.
- **Missing:** Scheduler component (how does `scheduled_at` become a job? nothing dispatches it), notification service, webhook *ingress* (Meta deauthorization + data-deletion callbacks are mandatory for app review), monitoring, rate limiting, and a token-refresh background job.
- **Change:** See improved architecture in `docs/02-architecture.md` — adds beat scheduler, webhook receiver, notifier, observability plane, and a token-lifecycle worker.

### §4 Common prerequisites
- **Good:** Privacy policy/terms URLs, demo screencast, test accounts, local + prod redirect URIs — all real app-review requirements people discover too late.
- **Missing:** **Data-deletion callback URL** (Meta requires a data deletion request endpoint or instructions URL), business verification (needed for Meta Advanced Access), and a staging environment with its own OAuth apps (never share OAuth clients between dev/prod).
- **Change:** Add per-environment OAuth app matrix (dev app / staging app / prod app per platform).

### §5 Platform prerequisites summary
- **Good:** Accurate at the summary level; the "permissions change over time, check the dashboard" warning is exactly right.
- **Outdated/incomplete (verified July 2026):** Instagram now has **two integration paths**: *Instagram API with Instagram Login* (scopes like `instagram_business_basic`, `instagram_business_content_publish`, **no Facebook Page required**) and the classic *Instagram API with Facebook Login* (`instagram_content_publish`, Page-linked). The PDF only describes the second. The first is now the simpler path for creator accounts.
- **Change:** Decide the Instagram path explicitly (see `docs/05-platform-requirements.md`); it changes onboarding UX and app review scope.

### §6 Instagram setup
- **Good:** Container flow is correct (create container → poll status → publish). Common-mistakes list is genuinely useful (public media URL, professional account, don't over-request permissions).
- **Missing:** Content-publishing quota handling — the API exposes `content_publishing_limit`; the app must check it before queueing, not discover it via errors. Missing carousel flow, Reels cover/thumbnail options, and the `expire`/error codes of containers (containers expire after ~24h; a slow scheduler can publish a dead container).
- **Production improvement:** Media URLs handed to Meta should be **time-limited signed URLs** from your bucket, not permanently public objects.

### §7 Facebook setup
- **Good:** Correct scope list (`pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `publish_video`); correct Page-token derivation from user token.
- **Missing:** Long-lived token exchange (short-lived user token → 60-day token → Page token), token expiry/deauth handling, and the fact that external users require **Advanced Access + Business Verification** through App Review.

### §8 LinkedIn setup
- **Good:** Personal-first, organization-later is the right sequencing; mentions versioned REST (`LinkedIn-Version` header) and URN-based posting — both real.
- **Missing:** Token lifetimes (60-day access tokens; refresh tokens are **not** granted to all apps — plan a reconnect UX), the `X-Restli-Protocol-Version: 2.0.0` header, and API version sunsetting (versions are supported ~1 year; pin + review quarterly).

### §9 YouTube setup
- **Good:** Resumable `videos.insert` is correct; quota awareness and OAuth consent-screen setup are called out.
- **Missing (important, verified July 2026):** Quota economics changed: `videos.insert` dropped from ~1,600 units to ~100 (Dec 2025), and since June 2026 `search.list` and `videos.insert` bill to separate daily buckets. Also missing: **unverified apps in "testing" mode get refresh tokens that expire in 7 days** (breaks scheduled posts silently), sensitive-scope verification, and the API **audit** requirement — un-audited projects can have uploads locked private. These three issues are the most common "works in dev, broken in prod" YouTube failures.

### §10 Minimal database design
- **Good:** Correct table decomposition — `post_drafts → post_targets → publish_jobs` with `audit_logs` is the right normalized spine; storing `api_response_json` and `external_post_id` is exactly right.
- **Missing:** `workspace_id` (multi-tenancy), unique constraints (`connected_accounts(user_id, platform, external_account_id)`), an **idempotency key** on `publish_jobs` (prevents double-posting on retry), token `key_version` for encryption-key rotation, `timezone` on scheduled posts, indexes (`publish_jobs(status, run_at)`), and `updated_at` everywhere. `password_hash` implies rolling your own auth — use Argon2id and email verification, or a managed provider.
- **Change:** Full revised schema in `docs/02-architecture.md` §6.

### §11 API endpoints
- **Good:** Small, coherent REST surface; OAuth start/callback per provider is right.
- **Missing:** `DELETE /connected-accounts/{id}` (disconnect + token revocation), `GET /connected-accounts`, webhook endpoints (`POST /webhooks/meta` incl. deauth + data deletion), notification prefs, health checks (`/healthz`, `/readyz`), and an SSE endpoint for live status (the doc says "polls or WebSocket/SSE" but defines no endpoint).
- **Change:** Versioned API (`/api/v1/...`) from day one; publish endpoint should accept an `Idempotency-Key` header.

### §12 Frontend screens
- **Good:** Complete screen inventory including admin-ish history + raw API logs; Settings screen with token reconnect shows lifecycle awareness.
- **Missing:** Platform validation feedback in preview (character counts, aspect-ratio warnings), scheduled-posts calendar view, notification center, and empty/error/loading states (the difference between demo and product).

### §13 Build phases
- **Good:** Mock-first, then one platform at a time — this is the correct de-risking order and mirrors what I'd tell a team.
- **Change:** Add Phase 0 (repo, CI/CD, lint, secrets scanning, Snyk gates) and make idempotency + state machine part of Phase 2, not an afterthought. Expanded roadmap in `docs/09-roadmap.md`.

### §14 Master prompt
- **Good:** Unusually good build prompt: mock publishers behind feature flags, encrypted tokens, background jobs, TODO markers. Env var list is a solid `.env.example` seed.
- **Missing:** No tests in deliverables, no security acceptance criteria (CSP, rate limits, authz checks), no migration tool named (use Alembic), `ENCRYPTION_KEY=` implies a single static key — should specify AES-256-GCM + key rotation/`key_version`, ideally KMS.

### §15 App review & production checklist
- **Good:** This is a strong checklist — reviewer instructions, screencast, per-permission justification, reconnect flow, rate-limit handling, manual approval before publish, per-platform validation.
- **Missing:** Data-deletion callback (Meta), backup/restore drill, alerting thresholds, on-call/runbook, dependency scanning, and rollback plan.

### §16 Development notes
- **Good:** All six notes are hard-won, correct advice (especially "never expose tokens in frontend" and "store all external post IDs").

### §17 Sources
- **Good:** Official docs only. **Improvement:** No retrieval dates; platform docs change monthly — always re-verify at build time (this analysis re-verified key facts July 2026; see `docs/12-references.md`).

---

## 2. Rollup

### Strengths (keep)
1. Official APIs + OAuth only; explicit anti-patterns (no scraping/passwords) — matches this project's non-negotiables.
2. Correct async architecture instinct: background jobs, job-per-platform, store raw responses.
3. Correct platform publish flows at the happy-path level (IG container, FB Page token, LinkedIn URN, YT resumable).
4. Mock-first phased build; feature flags per platform.
5. Realistic app-review preparation (screencast, test users, permission minimalism).

### Weaknesses (fix)
1. Hedged tech stack (two backends, three queues) — pick one.
2. Token *storage* covered, token *lifecycle* not (refresh, expiry, revocation, reconnect).
3. No idempotency anywhere → duplicate-post risk is real (retried job that actually succeeded).
4. Scheduling named but not designed (no dispatcher, no timezone/DST handling).
5. Auth hand-waved (`password_hash or auth_provider`).
6. Security is a checklist, not a design (no KMS, key rotation, SSRF defense for media fetching, upload scanning, CSP).

### Missing components (add)
| # | Component | Why it matters |
|---|-----------|----------------|
| 1 | Webhook receiver (Meta deauth + data deletion) | Mandatory for Meta app review; without it users can't revoke cleanly |
| 2 | Token-lifecycle worker (proactive refresh, expiry alerts) | Scheduled posts fail silently when tokens die |
| 3 | Notification service (email + in-app) | Required by context doc; publish failures must reach humans |
| 4 | Observability plane (Sentry, metrics, structured logs, alerts) | You cannot run schedulers blind |
| 5 | Rate limiting (inbound API + platform quota tracking) | IG/YT quotas are hard product constraints, not infra trivia |
| 6 | Idempotency keys + post state machine | Prevents duplicate posts, the worst user-facing failure |
| 7 | Media pipeline (validation, EXIF strip, thumbnail, signed URLs) | Platform rejections happen at media level |
| 8 | Multi-tenancy (`workspace_id`) | Cheap now, migration project later |
| 9 | CI/CD with security gates (Snyk code/SCA/IaC, secret scanning) | User requirement: verify security policy enforced in code |
| 10 | Staging environment + per-env OAuth apps | OAuth cannot be tested safely against prod apps |

### Better approaches (replace)
1. **SSE over WebSocket** for status: one-directional updates, simpler infra, works through proxies. WebSocket adds statefulness you don't need.
2. **Presigned upload URLs** (browser → bucket direct) instead of proxying media bytes through the API — cheaper, faster, keeps API stateless.
3. **Signed, expiring media URLs** for platform fetches instead of public bucket objects.
4. **Envelope encryption via KMS** instead of one `ENCRYPTION_KEY` env var — enables rotation and audit of decrypt calls.
5. **DB-driven scheduler** (`SELECT ... FOR UPDATE SKIP LOCKED` on due posts each minute) instead of enqueueing far-future Celery ETAs (broker restarts lose them; Redis ETA tasks pin memory).

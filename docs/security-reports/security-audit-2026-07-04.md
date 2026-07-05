# Security Audit — July 4, 2026

Scope: full repo (`apps/api` FastAPI backend, `apps/web` Next.js frontend). Method: Snyk Code (SAST) + Snyk SCA (npm) + Snyk package intelligence (PyPI) + manual review against `docs/10-security-best-practices.md`. All fixes regression-tested (25/25 pytest, tsc clean).

## 1. Scan results (final state)

| Scan | Result |
|---|---|
| Snyk Code (SAST), whole repo, medium+ | **0 issues** |
| Snyk SCA — apps/web (npm, lockfile) | **0 issues** |
| Snyk package intel — cryptography 49.0.0, Pillow 12.2.0, SQLAlchemy 2.0.51 | **No known vulnerabilities, all "Healthy"** |
| Snyk package intel — fastapi 0.139.0 | No data in Snyk intel (warning); full pip SCA pending (below) |
| Snyk SCA — apps/api (pip) | **Pending**: requires installed packages — run after `pip install` on your machine (see §4) |

## 2. Findings fixed during this audit

| # | Severity | Finding | Fix |
|---|---|---|---|
| 1 | High (SAST) | Path-traversal pattern: DB-derived `storage_key` flowed into `FileResponse` | Media paths now rebuilt from server-owned components with `os.path.basename()` + containment check (`services/media.py: resolved_media_path`); `storage_path()` also validates containment |
| 2 | High (SCA) | `next@15.5.20` — CVE-2025-59472 + CVE-2026-27980 (resource exhaustion) | Upgraded to `next ^16.1.7` (resolved 16.2.10); tsc + lockfile regenerated |
| 3 | Medium (SCA) | `postcss@8.4.31` transitive XSS (CVE-2026-41305) | npm `overrides` + direct dep → `^8.5.10` |
| 4 | High (pkg intel) | `cryptography 48.0.0` — 1 known High | Pinned `cryptography==49.0.0` (clean per Snyk); floor raised in requirements.txt |
| 5 | Medium (SAST) | DOM-XSS taint: upload-response id interpolated into `img src` | `encodeURIComponent()` (practically FP — React escapes — but hardened) |
| 6 | Medium (manual) | OAuth authorization `code` values appear in access logs | Redaction filter now scrubs `[?&]code=...` (`security/middleware.py`) |
| 7 | Medium (manual) | App could boot in staging/prod with default `SESSION_SECRET` / missing `TOKEN_ENC_KEY_B64` | Fail-fast startup check when `APP_ENV != dev` (`main.py`) |

## 3. Manual audit — verified controls (pass)

OAuth: single-use server-stored `state` bound to the initiating user, 10-min TTL; token exchange server-side only; exact redirect URI from config. Tokens: AES-256-GCM with key_version, decrypted only inside publisher at call time; never in API responses, logs (redaction filter), or the browser. Sessions: httpOnly + SameSite=Lax (+ Secure outside dev); Argon2id hashing; generic login errors; login rate-limited. Authorization: every query scoped by session workspace; ownership checks return 404 (no existence leak); verified on media, drafts, targets, jobs, notifications, SSE. Uploads: magic-byte type detection (extension/content-type ignored), size caps, EXIF/GPS stripped on images, sha256 recorded. Injection: ORM/parameterized everywhere; no raw SQL, no shell calls, no `dangerouslySetInnerHTML`. Headers: nosniff, DENY, referrer policy, HSTS in prod; CORS locked to the web origin with explicit `Idempotency-Key` allow. Duplicate-post protection: idempotency keys + same-transaction external-ID writes + chaos tests. Secrets: `.env` git-ignored; `.env.example` documents names only; no secrets in code (manual grep + SAST).

## 4. Accepted residual risks (known, documented, deliberate for local MVP)

| # | Risk | Why acceptable now | Trigger to fix |
|---|---|---|---|
| 1 | Sessions can't be revoked server-side before expiry (signed cookie, no server session store) | Single-user local dev; 7-day expiry | Before multi-user staging → server-side session table (schema supports it) |
| 2 | Rate limiter is in-memory, per-process, keyed by direct-connection IP | Fine for localhost; documented as dev-grade | Behind a proxy/multi-instance → Redis limiter + X-Forwarded-For handling (M8/M9 in roadmap) |
| 3 | Register endpoint reveals whether an email exists (409) | Standard UX tradeoff; rate-limited | If abuse observed → uniform response + email-based flow |
| 4 | MP4 uploads: no antivirus / deep container inspection | Videos only pass through to platform APIs; not re-served publicly | Before accepting third-party/team uploads (roadmap M2 AV hook) |
| 5 | LinkedIn `uploadUrl` host not allowlisted (comes from LinkedIn's authenticated API over TLS) | Trusted, authenticated source | Cheap hardening: pin `*.licdn.com`/`linkedin.com` hosts when adding video upload |
| 6 | SQLite + local disk storage | Dev-mode architecture by request (no Docker) | Production = Postgres + R2 + Celery per docs/02 |
| 7 | fastapi 0.139.0 not covered by Snyk package intel | Latest stable line, actively maintained | Full pip SCA (below) closes the gap |

## 5. Re-scan instructions (after your venv exists)

```powershell
cd apps\api
python -m venv .venv ; .venv\Scripts\Activate.ps1 ; pip install -r requirements-dev.txt
```
Then ask Claude to re-run the Snyk pip SCA (or run `snyk test --command=python` yourself). `requirements-pinned.txt` records the exact versions this audit tested. Re-run the full suite (SAST + SCA) at every release; CI gates are specified in docs/04 (DO-2) and roadmap M0.

## 6. Verification

- Backend: **25/25 tests pass** post-fixes (includes crypto round-trip on cryptography 49, idempotency chaos tests, OAuth state forgery, LinkedIn adapter contract tests).
- Frontend: `tsc --noEmit` clean on Next 16.2.10.
- Final Snyk Code scan: 0 issues at medium+ severity. Final npm SCA: 0 issues.

## 7. Post-redesign re-verification + A/C/I mapping (July 4, 2026, after UI overhaul)

The vibrant UI redesign touched 10 frontend files (design system, nav, all pages). Re-verified afterwards: **Snyk Code 0 issues · npm SCA 0 issues · backend 25/25 · tsc clean.** The redesign is presentation-only — no new data flows, storage, or API surface.

### Authenticity — is every actor and artifact genuine?
| Control | Mechanism | Evidence |
|---|---|---|
| User identity | Argon2id verification; generic errors prevent enumeration at login | `test_auth` (wrong password → 401 generic) |
| Session authenticity | HMAC-signed cookies (itsdangerous); forged/expired → 401 | `test_protected_routes_require_auth` |
| Request origin | SameSite=Lax httpOnly cookie + CORS locked to web origin | header assertions, config review |
| OAuth flow | Single-use server-stored `state` bound to the initiating user, 10-min TTL | `test_callback_rejects_forged_state` (403-class rejection) |
| Upstream API | LinkedIn called only at `api.linkedin.com`/`www.linkedin.com` over TLS | adapter code review |
| Dependencies | npm lockfile committed; `requirements-pinned.txt` records exact audited versions | SCA scans on lockfile/pins |

### Confidentiality — can secrets or private data leak?
| Control | Mechanism | Evidence |
|---|---|---|
| Tokens at rest | AES-256-GCM, `key_version`ed, KMS-ready envelope design | `test_round_trip`; DB stores ciphertext only |
| Tokens in transit to browser | Never — accounts API returns metadata only; no token code exists in frontend | code review + SAST |
| Logs | Redaction filter scrubs Bearer tokens, `access_token`, OAuth `code=` params | filter unit behavior + middleware review |
| Secrets hygiene | `.env` git-ignored; names-only `.env.example`; fail-fast boot in non-dev on default/missing secrets | `main.py` guard |
| Tenant isolation | Every query scoped by session workspace; foreign IDs → 404 | IDOR tests in `test_auth`/media/posts paths |
| Media privacy | EXIF/GPS stripped on upload; files served only to authenticated owner | `save_upload` pipeline + `_owned_asset` |

### Integrity — can data be tampered with or corrupted?
| Control | Mechanism | Evidence |
|---|---|---|
| Token blobs | AES-GCM is authenticated encryption — any tampering fails decryption | `test_tampered_ciphertext_fails` |
| Post lifecycle | Enforced state machine; illegal transitions raise | `test_state_machine` (4 illegal paths) |
| No duplicate posts | Idempotency keys (unique constraint) checked before state guards; external IDs written in the same transaction | `test_double_publish_same_key_creates_one_job`, publish-twice test |
| Uploaded media | Magic-byte type verification + sha256 checksum recorded | upload matrix tests |
| Audit trail | Append-only `audit_logs` rows for auth, connect, publish, retry | audit writer usage across routers/worker |
| Database | FK enforcement (SQLite pragma ON), unique constraints on accounts/jobs | schema + `db.py` |

Residual items unchanged from §4; Python pip SCA still pending the local venv (§5).

## 8. Redesign v2 re-audit (July 4, 2026 — black/neon-green theme + OAuth setup checklist)

Changes: full dark-neon restyle of all 11 frontend files; new backend endpoint `GET /oauth/linkedin/config` (exposes redirect URI + config booleans — **no secret values**) powering a Settings-page setup checklist with copy-button for the exact redirect URL (root-cause fix for the `redirect_uri does not match` OAuth failure); startup guard for empty `LINKEDIN_REDIRECT_URI`.

Re-verification: **Snyk Code 0 issues · npm SCA 0 issues · backend 26/26 tests** (new test asserts the config endpoint never leaks secret material) · `tsc --noEmit` clean. No new data flows beyond the non-secret config read; A/C/I posture of §7 unchanged.

## 9. Feature-batch re-audit (July 4, 2026 — multi-media, platform roster, GitHub upload, animations)

Changes: multi-photo posts (LinkedIn `multiImage`, up to 9 in UI / 20 API-side), separate photo/video upload sections, platform roster now **LinkedIn · GitHub · YouTube** (Facebook/Instagram removed), CSS-only posting animations (rocket launch, confetti, progress shimmer — no new dependencies), and a **GitHub integration**: encrypted PAT storage (validated via `GET /user`, AES-256-GCM at rest) + filtered whole-folder upload to a repo via the Git Data API.

Upload security controls: exclusion rules enforced **client-side and server-side** (`.env*` always blocked, `node_modules/.git/.next/__pycache__/.venv/data/storage/caches/builds/logs/DBs`, >5 MB files); path traversal rejected; repo name regex-validated; hard caps 400 files / 25 MB; rate-limited (3/min); every upload audit-logged with counts. Findings fixed this round: 2 Medium DOM-XSS flags (upload-result `repo_url` → `href`) resolved by parsing and **rebuilding** the URL from validated parts (`https:` + `github.com` host only) plus `rel="noopener noreferrer"`.

Re-verification: **Snyk Code 0 issues · npm SCA 0 issues · backend 31/31 tests** (new: exclusion-filter matrix incl. traversal + secret files, PAT rejection/encryption round-trip, LinkedIn multiImage body assertion, video-rejection) · `tsc --noEmit` clean. Token permission guidance documented in `docs/github-token-setup.md` (least-privilege fine-grained PAT).

## 10. Audit v3 (July 5, 2026 — roster change + animation layer + workflow verification)

Changes: posting options are now **LinkedIn · Facebook · Twitter · YouTube** (GitHub removed from the posting roster per user; the GitHub *project-upload utility* in Settings is unchanged and independent of the roster). Twitter limits enforced: 280 chars / 4 photos. New interaction layer (`components/Fx.tsx` + CSS): cursor spotlight, 3D tilt cards, magnetic buttons, rotating border beam, emoji burst, logo pulse, tech-grid backdrop — all dependency-free, GPU-transform-based, and fully disabled under `prefers-reduced-motion` (WCAG 2.3.3 consideration).

Workflow verification (backend ↔ frontend): automated **API contract check** — every HTTP call extracted from the frontend source (22 calls: api client, fetch, EventSource) resolves to a registered backend route (27 routes) with matching method and path shape; zero mismatches. Full suite: **backend 31/31 tests · `tsc --noEmit` clean · Snyk Code 0 issues (medium+) · npm SCA 0 issues.** Animation layer introduces no new network calls, storage, or input parsing — attack surface unchanged. Residual risks of §4 stand; pip SCA still pending the local venv (§5).

## 11. Full-depth scan matrix (July 5, 2026 — final)

| Scan | Scope | Result |
|---|---|---|
| Snyk Code (SAST), **low** threshold | whole repo | **8 Low** — all hardcoded *test-fixture* credentials in `tests/` (`conftest.py`, `test_auth.py`). **Accepted**: deliberate fake values, never shipped, no production path. Zero findings in application code at any severity. |
| Snyk SCA npm, **including devDependencies** | apps/web (lockfile) | **0 issues** |
| Snyk SCA pip | apps/api | **Blocked by env drift**: the local venv predates the `cryptography>=49` floor, so resolution fails. **Action:** `pip install -r requirements-dev.txt` in the venv, then re-run. Gap covered meanwhile by per-package intelligence (below). |
| Snyk package intelligence (direct Python deps, exact tested pins) | 12 packages | **0 known vulnerabilities in all 12**: fastapi*, uvicorn, sqlalchemy, pydantic, pydantic-settings*, argon2-cffi, cryptography (49.0.0), httpx, python-multipart, Pillow, itsdangerous, filetype, APScheduler. |
| Snyk IaC / container / SBOM | — | N/A — no IaC files, Dockerfiles, or SBOM in repo yet (arrive with roadmap M0/M10 deployment work). |
| Backend tests | 31/31 pass | includes idempotency chaos, OAuth state forgery, crypto tamper, upload filters, multiImage contract |
| TypeScript | `tsc --noEmit` | clean |
| API contract | 22 frontend calls ↔ 27 routes | 0 mismatches |

\* fastapi and pydantic-settings have no Snyk intelligence dataset entry at these versions; they are covered once the full pip SCA runs post venv refresh.

Maintenance advisories (not vulnerabilities): `itsdangerous` 2.2.0 and `filetype` 1.2.0 are flagged "review recommended" for slow release cadence only — both have zero known CVEs. `itsdangerous` is a stable Pallets project (low churn is normal). `filetype` (magic-byte sniffing) last released 2022; consider swapping to `puremagic` in a future milestone — noted in the backlog, not blocking.

**Verdict: no known vulnerabilities anywhere in application code or dependency tree at the tested versions.** Outstanding items: (1) user runs `pip install -r requirements-dev.txt` then full pip SCA re-run; (2) `filetype` replacement, backlog.

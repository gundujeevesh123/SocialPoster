# Social Posting Automation Platform — Architecture & Requirements Pack

Generated July 3, 2026 from `FounderLabs_Social_Posting_Automation_Guide.pdf` + `context_social.txt`, with platform facts re-verified against current documentation. This pack is the pre-implementation blueprint; code comes next.

## 1. Executive summary (Deliverable 1)

The goal is a production-grade web platform where a user uploads media once, connects Instagram, Facebook, LinkedIn, and YouTube via OAuth, generates per-platform captions, previews, and publishes now or on a schedule — using **official APIs only** (no scraping, no password storage, no browser automation), extensible to X, Threads, TikTok, and Pinterest.

The FounderLabs PDF is a good MVP guide with correct platform mechanics and the right async instincts (background jobs, encrypted tokens, mock-first build). It is **not yet a production blueprint**: it lacks token *lifecycle* management, idempotency (duplicate-post protection), a real scheduler design, Meta's mandatory deauth/data-deletion webhooks, notifications, observability, CI security gates, and multi-tenant modeling. This pack keeps its strengths and fills those gaps.

Recommended shape: **full-stack web application** — Next.js (Vercel) + FastAPI/Celery (Render) + PostgreSQL + Redis + Cloudflare R2 + KMS envelope encryption, with Snyk/gitleaks gates in CI so the security policy is *enforced in code* and verifiable by scan after the build (your Snyk MCP requirement — scans run once code exists, and at every release).

The two schedule-critical actions are bureaucratic, not technical: start **Meta Business Verification** and **Google OAuth verification/audit** in week 1 — they have multi-week lead times but don't block development thanks to dev-mode testing.

## 2. Document index

| Doc | Contents (deliverable #) |
|---|---|
| [docs/01-pdf-analysis.md](docs/01-pdf-analysis.md) | Section-by-section PDF critique; strengths/weaknesses/missing/better approaches (2, 3) |
| [docs/02-architecture.md](docs/02-architecture.md) | Improved production architecture + Mermaid diagrams, schema, token & scheduler design (4) |
| [docs/03-workflow.md](docs/03-workflow.md) | 40-step numbered end-to-end workflow, beginner-friendly (5) |
| [docs/04-project-requirements.md](docs/04-project-requirements.md) | Full requirements: frontend→deployment, prioritized (6) |
| [docs/05-platform-requirements.md](docs/05-platform-requirements.md) | Per-platform setup, scopes, reviews, limits — July 2026 verified (7) |
| [docs/06-api-keys-checklist.md](docs/06-api-keys-checklist.md) | Every account/key/secret/redirect/env var: why, where, when (8) |
| [docs/07-technology-comparison.md](docs/07-technology-comparison.md) | 7 technology face-offs + final stack ADR (9) |
| [docs/08-application-type.md](docs/08-application-type.md) | Artifact vs web vs desktop vs mobile vs hybrid (10) |
| [docs/09-roadmap.md](docs/09-roadmap.md) | Milestones M0–M10 with testing + completion criteria (11) |
| [docs/10-security-best-practices.md](docs/10-security-best-practices.md) | Security controls mapped to code/CI verification (12) |
| [docs/11-production-checklist-and-risks.md](docs/11-production-checklist-and-risks.md) | 30-point launch checklist + 14 risks with mitigations (13, 14) |
| [docs/12-references.md](docs/12-references.md) | Official documentation links (15) |

## 3. Action plan — build in exactly this order

1. **Today:** Create Meta app, LinkedIn app, Google Cloud project (dev instances). Kick off Meta Business Verification and write the privacy policy — longest lead times. *(docs/05, 06)*
2. **M0 (this week):** Repo + Docker compose + CI with Snyk code/SCA + gitleaks gates. Security rails before features. *(docs/09 M0)*
3. **M1:** Auth + workspaces + full DB schema via migrations. *(02 §6)*
4. **M2:** Media pipeline (presigned uploads, validation, EXIF strip, thumbnails).
5. **M3:** The core loop with **mock publishers** — drafts, state machine, Celery jobs, idempotency, SSE live status. Demoable end-to-end without any platform approvals.
6. **M4:** OAuth for Meta + LinkedIn + Google with KMS-encrypted tokens, refresh worker, deauth webhooks.
7. **M5:** First real platform (Facebook Page — easiest) behind a feature flag.
8. **M6:** Instagram (container flow), YouTube (resumable + quota meter), LinkedIn media.
9. **M7:** Scheduling engine + calendar + timezones.
10. **M8:** Notifications + monitoring/alerts.
11. **M9:** Security hardening — full Snyk suite (code, SCA, IaC, container) to zero high/critical + authz/OAuth pen-check. *(Your post-build verification gate.)*
12. **M10:** App reviews (Meta Advanced Access, LinkedIn products, Google verification/audit) → production checklist → launch.

Start with step 1 and M0 today; everything through M3 requires zero platform approvals.

---

## 4. The app (built July 3, 2026 — LinkedIn live, FB/IG/YT mocked)

Monorepo: `apps/api` (FastAPI + SQLite + in-process worker — no Docker needed) and `apps/web` (Next.js + Tailwind). LinkedIn posting uses the official versioned Posts API; other platforms run as mock publishers behind `ENABLE_*_REAL` flags until their milestones.

### Run locally (Windows, two PowerShell terminals)

Prereqs: Python 3.11+ and Node 18.18+ (`python --version`, `node --version`).

**Terminal 1 — API:**
```powershell
cd apps\api
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env
# EDIT .env — required values:
#   TOKEN_ENC_KEY_B64  -> python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
#   SESSION_SECRET     -> python -c "import secrets;print(secrets.token_urlsafe(48))"
#   LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET  (from developer.linkedin.com > your app > Auth)
uvicorn app.main:app --port 8000
```

**Terminal 2 — Web:**
```powershell
cd apps\web
npm install
npm run dev
```

Open **http://localhost:3000** → register → Settings → Connect LinkedIn → Create → Post now.

### Test checklist (what to verify before approving the GitHub push)
1. Register + login + logout work; weak password rejected.
2. Settings → Connect LinkedIn → consent screen → redirected back as "Connected".
3. Create post: upload a JPG, write caption, select LinkedIn + Facebook (mock), Post now.
4. Status page shows live progress; LinkedIn card ends **published** with a working post link; the post is on your LinkedIn profile.
5. History lists both targets; mock Facebook shows a fake URL.
6. Schedule a post 2 minutes ahead → it publishes on time (worker runs inside the API process).
7. Caption with `[fail]` on a mock platform → fails, shows error, Retry works.

### Run backend tests
```powershell
cd apps\api
.venv\Scripts\Activate.ps1
pytest -q
```

Troubleshooting: LinkedIn "invalid redirect" → the app's Authorized redirect URL must be exactly `http://localhost:8000/api/v1/oauth/linkedin/callback`. "LinkedIn is not configured" → fill both LINKEDIN_ vars in `apps/api/.env` and restart uvicorn. Port already in use → change `--port` and `API_ORIGIN` env for the web app accordingly.

# Phase 6 — Accounts, API Keys & Secrets Checklist

Legend: D = needed for Development, T = Testing/staging + app review, P = Production. Create everything per-environment; never reuse prod OAuth apps in dev.

## A. Accounts & prerequisites

| # | Item | Why needed | Where created | When | Env |
|---|---|---|---|---|---|
| 1 | Domain + subdomains (`app.`, `api.`, `staging.`) | OAuth redirect URIs, consent screens require real HTTPS domains | Registrar + DNS | Before any OAuth app review | T, P |
| 2 | Privacy Policy URL (public) | Required by Meta, LinkedIn, Google consent screens | Your site | Before app creation/review | D, T, P |
| 3 | Terms of Service URL | Required/expected by reviews | Your site | Before review | T, P |
| 4 | Data Deletion instructions URL / callback | Meta app requirement | Your app + Meta dashboard | Before Meta review | T, P |
| 5 | Meta developer account | Owns Meta app | developers.facebook.com | Week 1 | D |
| 6 | Meta Business Verification | Advanced Access for external users | business.facebook.com | Start week 1 (1–3 wks lead) | P |
| 7 | LinkedIn developer app + Company Page association | App verification requirement | developer.linkedin.com | Week 1 | D, T, P |
| 8 | Google Cloud project (×3 envs) | YouTube API + OAuth clients | console.cloud.google.com | Week 1 | D, T, P |
| 9 | Test assets: IG professional test account, FB Test Page, LinkedIn test profile, YouTube test channel | Never test on the real brand | Each platform | Before first real publish | D, T |
| 10 | Demo screencast of full flow | Required in Meta/LinkedIn/Google reviews | Record on staging | Before each review | T |

## B. OAuth clients & platform secrets

| # | Secret | Why | Where created | Env vars | Env |
|---|---|---|---|---|---|
| 11 | Meta App ID/Secret | FB + IG OAuth + Graph calls | Meta app dashboard | `META_APP_ID`, `META_APP_SECRET` | D, T, P (separate apps) |
| 12 | Meta redirect URIs | Exact-match callback allowlist | Meta app > Facebook Login settings | `META_REDIRECT_URI` | D, T, P |
| 13 | Meta webhook verify token | Verifies deauth/data-deletion webhook subscription | You generate; paste in Meta dashboard | `META_WEBHOOK_VERIFY_TOKEN` | T, P |
| 14 | LinkedIn Client ID/Secret | LinkedIn OAuth | LinkedIn app > Auth tab | `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET` | D, T, P |
| 15 | LinkedIn redirect URIs | Callback allowlist | LinkedIn app > Auth tab | `LINKEDIN_REDIRECT_URI` | D, T, P |
| 16 | LinkedIn API version pin | Mandatory `LinkedIn-Version` header | Config (not dashboard) | `LINKEDIN_API_VERSION=YYYYMM` | D, T, P |
| 17 | Google OAuth Client ID/Secret (Web) | YouTube OAuth | GCP > Credentials | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | D, T, P |
| 18 | Google redirect URIs | Callback allowlist | GCP > Credentials | `GOOGLE_REDIRECT_URI` | D, T, P |
| 19 | OAuth consent screen (Testing → Production) | 7-day refresh-token expiry in Testing kills schedules | GCP > OAuth consent screen | — | T→P gate |

## C. Application infrastructure secrets

| # | Secret | Why | Where | Env vars | Env |
|---|---|---|---|---|---|
| 20 | Database URL | Postgres connection | Managed DB provider | `DATABASE_URL` | D, T, P |
| 21 | Redis URL | Broker + cache | Managed Redis | `REDIS_URL` | D, T, P |
| 22 | KMS key id / data key | Envelope encryption of OAuth tokens | Cloud KMS | `KMS_KEY_ID` (+ SDK creds) | T, P (D: local key `TOKEN_ENC_KEY`) |
| 23 | App session secret | Sign/verify session cookies/JWT | Generate 32+ random bytes | `SESSION_SECRET` | D, T, P (unique each) |
| 24 | Object storage keys + bucket | Media storage, presigned URLs | R2/S3 console | `S3_ENDPOINT`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET` | D (MinIO), T, P |
| 25 | LLM API key | Caption generation | OpenAI/Anthropic console | `LLM_API_KEY`, `LLM_PROVIDER` | D, T, P |
| 26 | Email API key | Notifications | Resend/Postmark | `EMAIL_API_KEY`, `EMAIL_FROM` | T, P |
| 27 | Sentry DSN | Error tracking | sentry.io | `SENTRY_DSN` | T, P |
| 28 | App base URLs | Redirect building, links in email | Config | `APP_BASE_URL`, `API_BASE_URL` | D, T, P |
| 29 | Snyk token | CI security gates (code/SCA/IaC/container) | app.snyk.io | CI secret `SNYK_TOKEN` | CI |
| 30 | GitHub Actions secrets store | Holds deploy + scan credentials | repo settings | — | CI |

## D. Rules that make this checklist safe
1. Every secret lives in the platform secret store (Render env groups / Vercel envs / GitHub Actions secrets) — never committed; `.env.example` documents names only.
2. Rotation calendar: session secret + storage keys yearly; platform secrets on incident; KMS key via `key_version` re-wrap. Document owner per secret.
3. gitleaks in CI blocks accidental commits; Snyk verifies dependency and code posture on every PR (this is the enforcement point for "security policy in code").
4. Dev uses mock publishers by default (`ENABLE_<PLATFORM>_REAL=false`) so no real secrets are needed until Phase-4 integration.

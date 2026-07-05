# Phase 5 — Platform Requirements (verified July 2026)

⚠️ Platform rules change monthly. Facts below were re-verified against current docs/search in July 2026; anything marked **VERIFY** must be re-checked in the developer dashboard the week you implement it.

## Token lifetimes cheat sheet

| Platform | Access token | Refresh mechanism | Practical consequence |
|---|---|---|---|
| Meta (FB/IG w/ FB Login) | Short-lived 1h → exchange for long-lived ~60d; Page tokens from long-lived user token effectively don't expire | Re-exchange before expiry | Refresh worker + reconnect UX |
| Instagram (Instagram Login path) | Long-lived ~60d | Refresh endpoint while valid | Refresh worker |
| LinkedIn | ~60d | Refresh tokens NOT granted to all apps (**VERIFY** for yours) | Plan mandatory reconnect UX every ~60d |
| Google/YouTube | 1h | Refresh token long-lived, BUT expires in **7 days while OAuth consent screen is in "Testing"**; revoked if unused 6 months | Publish consent screen + verification before relying on schedules |

---

## 1. Instagram

**Decision first:** two official paths.

| | Instagram API with **Instagram Login** | Instagram API with **Facebook Login** |
|---|---|---|
| Facebook Page required | No | Yes (IG account linked to Page) |
| Scopes | `instagram_business_basic`, `instagram_business_content_publish` | `instagram_content_publish`, `pages_show_list`, `instagram_basic`, `pages_read_engagement` |
| Best for | Creators/businesses without Page ops | Brands already managing FB Pages; single Meta connect flow |

Recommendation: since this app posts to Facebook anyway, use **Facebook Login path** for one unified Meta OAuth; add Instagram-Login path later for Page-less users.

- Developer account: developers.facebook.com — create developer account.
- Project creation: Create Meta App (type: Business).
- OAuth setup: Add Facebook Login product (or Instagram > API setup for the IG-Login path); set Valid OAuth Redirect URIs exactly per environment.
- Permissions/scopes: minimum set above; each permission needs written justification for review.
- App review: Development mode works for app roles (admin/developer/tester) without review. External users require **Advanced Access** → App Review + usually **Business Verification** (legal docs, can take 1–3 weeks).
- Redirect URLs: `https://app.<domain>/api/v1/oauth/meta/callback` (prod), staging + `http://localhost:8000/...` (dev app only).
- Keys/secrets: `META_APP_ID`, `META_APP_SECRET` per environment.
- Rate limits: Content publishing limited per IG account per rolling 24h. Sources conflict (25 vs 50 vs 100/day; tier-dependent) — **do not hardcode**: call `GET /{ig-user-id}/content_publishing_limit` and track in Redis. General Graph API call limits also apply per app/user.
- Publishing mechanics: container flow (`/media` → poll `status_code` = FINISHED → `/media_publish`); media must be fetchable by Meta (signed URL); containers expire (~24h) — publish promptly. Carousels: children containers → carousel container.
- Testing: test users/roles in dev mode; a dedicated test IG professional account + test Page. Never your main brand account first.
- Production: Advanced Access approved, Business Verification done, deauth + data deletion callbacks live, privacy policy URL public.
- Docs: developers.facebook.com/docs/instagram-platform/content-publishing/

## 2. Facebook (Pages)

- Developer account/app: same Meta app as above.
- OAuth: Facebook Login product; same redirect discipline.
- Permissions: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`; `publish_video` **VERIFY** current name for Page video uploads.
- Flow: user token → long-lived exchange → `GET /me/accounts` → store selected Page + Page access token (encrypted).
- App review: same Advanced Access + Business Verification story as Instagram.
- Rate limits: Pages/Graph API rate limits per app + per Page; handle error codes 4/17/32 with backoff.
- Testing: create a Test Page; dev-mode roles.
- Production: approved permissions; webhook subscription for deauth.
- Docs: developers.facebook.com/docs/pages-api/

## 3. LinkedIn

- Developer account: developer.linkedin.com; create app; **verify the app against a LinkedIn Company Page** (required).
- Products: request **"Share on LinkedIn"** (self-serve; grants `w_member_social` for member posting) + **"Sign In with LinkedIn using OpenID Connect"** (identity). Organization posting requires **Community Management API** approval (application + review; slower — do later).
- OAuth setup: Authorized redirect URLs exact-match; Authorization Code flow.
- Scopes: `openid profile email` + `w_member_social` (member). Org posting later: `w_organization_social` + admin URN checks.
- Headers (mandatory): `LinkedIn-Version: YYYYMM` (pin a version, e.g. current month at build; each version supported ≥1 year) and `X-Restli-Protocol-Version: 2.0.0`.
- API: **Posts API** (`/rest/posts`) — the older ugcPosts is legacy; media upload via Images/Videos API → URN → post.
- App review: product access requests reviewed by LinkedIn; personal posting is fast, Community Management can take weeks.
- Keys: `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET` per environment.
- Rate limits: per-app and per-member daily limits (not always published; watch `429` + `Retry-After`). **VERIFY** current numbers in dashboard analytics.
- Token life: 60-day access tokens; refresh tokens only for select programs — build reconnect flow as the default.
- Testing: your own member account; LinkedIn has no sandbox — use a low-follower test profile and delete test posts.
- Production: verified app, approved products, privacy policy, brand-compliant button/UX.
- Docs: learn.microsoft.com/linkedin/ (Posts API under Community Management docs).

## 4. YouTube

- Developer account: console.cloud.google.com — create Google Cloud project per environment.
- Enable API: YouTube Data API v3.
- OAuth setup: OAuth consent screen (app name, support email, authorized domain, privacy policy, scopes) + OAuth Client ID (Web application) with exact redirect URIs.
- Scopes: `https://www.googleapis.com/auth/youtube.upload` (upload only — prefer narrowest); avoid full `youtube` scope unless needed.
- Consent screen status: "Testing" mode = max 100 test users and **refresh tokens expire after 7 days** — unusable for scheduling. Move to "In production" + complete **OAuth verification** (sensitive scope review; needs domain verification, privacy policy, demo video; days–weeks).
- API audit: **VERIFY** current policy — historically, API projects that haven't completed a compliance audit have uploads restricted/locked private. Budget time for the audit form before launch.
- Quota (changed recently — verified): default 10,000 units/day; `videos.insert` cost dropped from ~1,600 to ~100 units (Dec 2025); since June 2026, `videos.insert` and `search.list` bill to **separate daily buckets** (~100 calls/day each). Practical ceiling ≈ 100 uploads/day/project until you pass a quota-increase audit (weeks–months). Build a per-day upload budget meter + user-facing error.
- Publishing: resumable upload (`uploadType=resumable`), then optional thumbnail set (`thumbnails.set`, needs channel eligibility); `status.privacyStatus` = public/unlisted/private/scheduled (`publishAt` requires private until publish time).
- Keys: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` per environment. (API keys are only for public read calls — uploads are OAuth-only.)
- Testing: test channel; testing-mode consent screen is fine for dev (expect 7-day re-consent).
- Production: consent screen "In production", verification passed, audit submitted, quota plan documented.
- Docs: developers.google.com/youtube/v3/docs/videos/insert, .../guides/uploading_a_video, .../determine_quota_cost.

---

## Cross-platform gotchas worth engineering for
1. **Meta review lead time** (business verification) and **YouTube verification/audit** are the long poles — start both in week 1, in parallel with development.
2. Rate/publishing limits are *product* constraints: show remaining quota in UI, don't just fail jobs.
3. Media specs differ (aspect ratios, durations, sizes) — encode a per-platform validation table and enforce at preview time; keep it in config, not code, so future platforms are data-only additions where possible.
4. Every platform can revoke tokens server-side at any time — deauth webhooks (Meta) + 401-triggered `requires_action` handling (all) are core flows, not edge cases.

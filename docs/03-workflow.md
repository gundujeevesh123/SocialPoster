# Phase 3 — End-to-End Workflow (Beginner-Friendly, Numbered)

Every step says *what happens* and *why it exists*. Steps marked 🔒 are security-critical.

## A. User registration
1. User opens the app and signs up with email + password (or magic link). Why: identity anchor for everything they connect later.
2. 🔒 Backend hashes the password with **Argon2id** (never stores the password itself) and creates the user + a personal workspace row.
3. Backend emails a verification link (signed, expiring token). User clicks; account becomes `verified`. Why: prevents signup with someone else's email and is required before connecting real social accounts.
4. Backend issues a session — httpOnly, Secure cookie. 🔒 Why httpOnly: JavaScript (and any XSS payload) cannot read it.

## B. OAuth connection (repeated per platform)
5. User opens **Connect Accounts** and clicks e.g. "Connect Meta".
6. Backend builds the provider authorization URL containing: client_id, exact registered redirect URI, requested scopes (minimum only), and 🔒 a random `state` value (+ PKCE where supported). `state` is stored server-side. Why: `state` blocks CSRF — an attacker can't trick the callback into attaching *their* account to *your* session.
7. User is redirected to the platform (instagram/facebook/linkedin/google consent screen) and approves.
8. Platform redirects back to `GET /api/v1/oauth/{provider}/callback?code=...&state=...`.
9. 🔒 Backend verifies `state` matches, then exchanges `code` + client_secret for tokens **server-side**. The browser never sees platform tokens.
10. Backend fetches account metadata (IG business account ID, FB Pages list, LinkedIn member URN, YouTube channel) so the user can pick which page/channel to use.

## C. Token storage
11. 🔒 Backend encrypts access + refresh tokens with AES-256-GCM using a KMS-wrapped data key, and stores ciphertext + nonce + `key_version` in `connected_accounts`. Why envelope encryption: a DB dump alone reveals nothing; decryption requires KMS, which is access-controlled and audited.
12. Backend records scopes granted and `token_expires_at`, then writes an `audit_logs` row ("account_connected").
13. A background job refreshes tokens before expiry where the platform allows (Meta long-lived, Google refresh tokens) and flags accounts needing manual reconnect (LinkedIn ~60 days) 7 days early, via notification. Why: scheduled posts must not die silently with expired tokens.

## D. Media upload
14. User drags a file onto **Create Post**. Frontend requests an upload slot: `POST /api/v1/media/presign` (sends filename, type, size).
15. Backend validates type/size against platform ceilings, then returns a **presigned PUT URL** for the bucket. Why presigned: media bytes go browser→storage directly; your API stays fast and stateless.
16. Browser uploads to the bucket; backend records the `media_assets` row.
17. 🔒 Async pipeline then: verifies real file type (magic bytes, not extension), strips EXIF/GPS metadata, runs antivirus scan, extracts dimensions/duration, generates thumbnail. Why: uploaded files are untrusted input.
18. UI shows per-platform validation results immediately (e.g., "video too long for Reels") — fail at edit time, not publish time.

## E. Caption generation
19. User writes a master caption and clicks **Generate per-platform captions**.
20. Backend calls the LLM API with platform constraints (IG: hashtags, 2,200 chars; LinkedIn: professional tone, 3,000; YouTube: title ≤100 + description; FB: casual) and returns editable drafts. Why editable: AI output is a starting point; the user owns the final text.
21. Results are cached by (media, caption, platform) hash to avoid paying twice for regenerations.

## F. Preview
22. User sees one preview card per selected platform, styled like the platform, with live character counts and validation warnings.
23. User edits captions/titles/privacy per platform; each edit re-validates. `post_targets` rows are saved (autosave).
24. User picks **Post Now** or **Schedule** (date + time + timezone; stored as UTC + timezone).

## G. Publishing
25. User confirms in the publish modal (explicit manual approval — prevents accidental posting).
26. Frontend calls `POST /api/v1/posts/{id}/publish` with an **Idempotency-Key**. Duplicate clicks return the same result instead of double-posting.
27. Backend validates everything again server-side (never trust the client), checks platform quota trackers, creates one `publish_jobs` row per target, and enqueues them. Responds `202` immediately.
28. A worker claims a job and transitions the target `queued → publishing`.
29. Platform-specific adapter runs:
    - **Facebook:** POST to Page feed/photos/videos with the stored Page token.
    - **Instagram:** create media container (signed media URL + caption) → poll container status until `FINISHED` → `media_publish`. Containers expire; publish promptly.
    - **LinkedIn:** upload media → get URN → create post with author URN + commentary (versioned headers).
    - **YouTube:** resumable `videos.insert` upload with title/description/tags/privacy; resume on interrupt.
30. Success: worker stores `external_post_id`, permalink URL, and the raw API response in the same transaction as the status change. Why same transaction: crash-safety — you can never have a published post without a recorded ID.
31. Failure: worker classifies the error — *retryable* (5xx, rate limit → exponential backoff + jitter, max 5 attempts) vs *permanent* (bad media, revoked token → fail now, tell the user what to fix). 🔒 Revoked token also flips the account to `requires_action`.

## H. Status updates
32. Workers publish status events to Redis pub/sub; the API forwards them to the browser over **SSE** (`GET /api/v1/posts/{id}/events`).
33. The Live Status page shows each platform card moving through Pending → Uploading → Published (with link) or Failed (with human-readable reason + Retry button).
34. Retry button calls `POST /api/v1/jobs/{id}/retry` — allowed only from `failed`, and the idempotency check runs again first.

## I. Audit logs
35. Every meaningful action (signup, connect, disconnect, draft create/edit, publish attempt, retry, token refresh, webhook received) appends an `audit_logs` row: who, what, when, request id, platform. 🔒 Never tokens or media contents.
36. Post History reads from drafts + jobs + audit trail: filter by platform/status/date, view raw API response per attempt (admin only).

## J. Notifications
37. The notifier worker listens to job events and sends: in-app notification always; email on final failure, token expiring, and (optional) publish success digest.
38. Webhook receiver handles Meta **deauthorize** and **data deletion** callbacks: marks the account revoked, pauses affected scheduled posts, notifies the user, and (for data deletion) runs the documented deletion workflow and returns the confirmation code Meta expects.
39. Weekly digest (optional): what published, what failed, tokens expiring soon.
40. Everything above emits metrics (publish success rate, job latency, queue depth, token-refresh failures) to dashboards with alert thresholds — so the *operator* gets notified before users notice.

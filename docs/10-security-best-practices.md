# Security Best Practices (Deliverable 12)

Organizing principle: every control below must be **enforceable and verifiable in code or CI** — this is the list the post-build Snyk MCP verification (code, SCA, IaC, container scans) and manual review will be checked against. Each item has a verification method.

## 1. OAuth & platform tokens (crown jewels)
| Control | Implementation | Verified by |
|---|---|---|
| Confidential client only | Token exchange server-side; secrets never shipped to browser | Code review + Snyk code scan (no secrets in frontend bundle) |
| CSRF-proof flows | Random single-use `state` (server-stored, TTL 10 min) + PKCE where supported | Integration tests (state mismatch → 403) |
| Exact redirect URIs | Per-env allowlists in each provider dashboard; no wildcards | Checklist docs/06 + config test |
| Minimum scopes | Scope constants per adapter; review-time justification doc | Code review |
| Encryption at rest | AES-256-GCM envelope encryption; KMS-wrapped DEK; `nonce` + `key_version` columns; rotation job | Unit test (round-trip, rotation), DB inspection (ciphertext only) |
| Decrypt at point of use | Only workers decrypt, only at API-call time; never cached to disk | Code review, grep-gate in CI for decrypt calls outside adapters |
| Revocation handling | Meta deauth webhook + 401→`requires_action` + user notification; disconnect calls provider revoke endpoint | Webhook signature tests |
| No tokens in telemetry | Log scrubber middleware; Sentry `before_send` redaction; SSE/API responses never include tokens | Log-audit test (publish a canary token, assert absent from logs) |

## 2. Application authentication & authorization
- Argon2id password hashing (memory-hard); constant-time comparisons; generic auth error messages.
- Sessions: httpOnly + Secure + SameSite=Lax; rotation on privilege change; server-side revocation list.
- Every data query scoped by `workspace_id` from the session — never from request params (kills IDOR class). One shared dependency (`get_current_workspace`) so it can't be forgotten per-endpoint.
- Rate limits: login 5/min/IP with backoff; publish 10/min/user; global 60 req/min/user. 429 + Retry-After.
- MFA (TOTP) available; enforced for workspace owners before production.

## 3. Input, media, and SSRF
- Pydantic models on every endpoint; strict types; max lengths mirroring platform limits.
- Media: magic-byte type check (never trust extension/Content-Type), size ceilings, EXIF/GPS strip, AV scan before any platform sees the file, checksum recorded.
- SSRF: workers fetch media **only** from your own bucket hostnames; no user-supplied fetch URLs; HTTP client with redirects disabled + private-IP block, as defense in depth.
- SQL: ORM/parameterized only — Snyk code scan flags string-built queries.

## 4. Secrets & configuration
- Secret manager per environment; `.env` git-ignored; `.env.example` names only; gitleaks CI gate.
- Distinct secrets per environment (a staging leak must not open prod).
- Rotation calendar with owners (docs/06 §D); KMS `key_version` re-wrap path tested before it's needed.
- Feature flags (`ENABLE_<PLATFORM>_REAL`) default **off** outside prod.

## 5. Transport & headers
- TLS 1.2+ everywhere (platform-managed certs); HSTS incl. subdomains.
- CSP (default-src 'self' + explicit allowlist), X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy strict-origin-when-cross-origin, Permissions-Policy minimal.
- CORS: exact frontend origin only; credentials mode deliberate.

## 6. Supply chain & CI enforcement (the Snyk layer)
- PR gate: `snyk code test` (SAST) + `snyk test` (SCA) fail on high/critical; `snyk iac test` on infra files; `snyk container test` on built images.
- `snyk monitor` weekly for drift alerts on main.
- Lockfiles committed; Renovate/Dependabot with grouped weekly PRs; no `latest` tags in Docker.
- Post-build verification (user requirement): run the full Snyk MCP suite against the repo and archive reports in `docs/security-reports/` — repeat per release.

## 7. Logging, audit & privacy
- Structured JSON logs with request IDs end-to-end (API → queue → worker).
- Append-only audit log (who/what/when/where) for auth, connect/disconnect, publish, retry, webhook, token refresh. No secrets, no media payloads, minimal PII.
- Data deletion: user-initiated account deletion removes tokens (+ provider revoke), media, and PII within SLA; Meta data-deletion callback implemented and returns confirmation code.
- Retention: raw API responses 90 days, audit logs 1 year (configurable).

## 8. Operational security
- Alerts on: webhook signature failures (attack probe), token-refresh failure bursts, publish-failure spikes, queue backlog.
- Backup restore drill quarterly; incident runbook (revoke → rotate → notify → postmortem).
- Principle of least privilege for cloud IAM: API role can't read KMS admin, workers can't drop tables, CI deploy key scoped per service.

## 9. Anti-requirements (explicitly forbidden — from project constraints)
- ❌ Browser automation / headless posting. ❌ Storing user platform passwords. ❌ Scraping. ❌ Unofficial APIs. ❌ Tokens in localStorage/sessionStorage or any frontend persistence. ❌ Shared OAuth apps across environments. ❌ Public bucket objects.

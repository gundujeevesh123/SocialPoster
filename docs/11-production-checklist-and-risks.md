# Production Deployment Checklist (Deliverable 13) & Risks (Deliverable 14)

## A. Production deployment checklist

### Infrastructure
- [ ] 1. Prod environment fully separate (DB, Redis, bucket, secrets, OAuth apps).
- [ ] 2. Custom domains + TLS live (`app.`, `api.`); HSTS on; DNS CAA set.
- [ ] 3. Managed Postgres: PITR on, daily snapshots, connection pooling (pgbouncer) configured.
- [ ] 4. Redis: persistence (AOF) on for broker DB; maxmemory policy set; separate logical DBs for broker vs cache.
- [ ] 5. Autoscaling/instance counts: ≥2 API instances, ≥2 workers, exactly 1 beat (or locked leader).
- [ ] 6. R2 bucket: versioning on, lifecycle rules on, private ACL verified.

### Security gates
- [ ] 7. Full Snyk suite (code/SCA/IaC/container) — zero high/critical; report archived.
- [ ] 8. gitleaks history scan clean; all secrets confirmed in secret manager only.
- [ ] 9. Security headers verified on prod URL (Mozilla Observatory ≥ A).
- [ ] 10. Authz spot-check: cross-workspace IDOR attempts return 404/403.
- [ ] 11. KMS key rotation runbook tested once; decrypt audit trail visible.
- [ ] 12. Webhook endpoints verify signatures; replay of an old payload rejected.

### Platform readiness
- [ ] 13. Meta: Business Verification approved; Advanced Access for all used permissions; deauth + data-deletion callbacks registered and tested; app switched to Live.
- [ ] 14. LinkedIn: app verified; Share on LinkedIn approved; version header pinned + calendar reminder to review quarterly.
- [ ] 15. Google: consent screen In production; OAuth verification passed; compliance audit submitted/passed; quota plan documented (uploads/day ceiling surfaced in UI).
- [ ] 16. Privacy policy, ToS, data-deletion pages live and linked in every consent screen.
- [ ] 17. Contract tests green against test accounts on all four platforms, from prod infra.

### Reliability & operations
- [ ] 18. Sentry receiving from web/API/workers with release tags; source maps uploaded.
- [ ] 19. Dashboards live: publish success rate, queue depth, scheduler lag, quota meters.
- [ ] 20. Alert rules fire-drilled (kill worker → page within 10 min).
- [ ] 21. `/healthz`+`/readyz` wired to platform health checks; uptime monitor + status page.
- [ ] 22. Backup restore drill completed and timed; RPO/RTO documented.
- [ ] 23. Rollback tested: previous image redeploy < 5 min; migrations backwards-compatible.
- [ ] 24. Load test passed (100 concurrent publishes, 1k scheduled dispatch < 60 s).
- [ ] 25. 1-week staging soak: zero missed schedules, zero duplicate posts.
- [ ] 26. Runbook covers: token revoked storms, platform outage, quota exhaustion, queue backlog, webhook flood.

### Product/legal
- [ ] 27. Manual-approval-before-publish default ON; per-platform validation blocking.
- [ ] 28. User-facing quota meters (IG daily publishes, YT daily uploads).
- [ ] 29. Account deletion flow (self-serve) tested end-to-end incl. provider revokes.
- [ ] 30. Platform ToS re-read for automation clauses (all four) — dated sign-off in repo.

## B. Risks & mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Platform API/permission changes break publishing (Graph versions retire; LinkedIn versions sunset ~yearly) | High | High | Pin versions; quarterly upgrade calendar; contract tests in CI against test accounts; adapters isolate blast radius |
| 2 | App review rejection/delay (Meta, LinkedIn, Google) | High | High (blocks external users) | Start Track B week 1; minimal scopes; polished screencast + reviewer creds; dev-mode demo unblocks own-account usage meanwhile |
| 3 | Duplicate posts on retry | Medium | High (user trust) | Idempotency keys, same-transaction ID writes, chaos tests in CI (M3) |
| 4 | Silent token expiry kills scheduled posts | High | High | Refresh worker, 7-day expiry warnings, `requires_action` state, reconnect UX; Google consent screen to production early (7-day trap) |
| 5 | YouTube quota ceiling (~100 uploads/day/project; audit takes weeks–months) | Medium | Medium | Quota meter, per-user daily caps, submit quota audit early, queue-and-spread strategy |
| 6 | IG publishing limit surprises (25–100/day, tier-dependent) | Medium | Medium | Query `content_publishing_limit` live; enqueue-time budget check; surface remaining quota |
| 7 | Token/DB breach | Low | Critical | Envelope encryption + KMS (dump alone useless), least-privilege IAM, decrypt audit, rotation runbook, alerting |
| 8 | Secret leakage via repo/logs | Medium | Critical | gitleaks gate, log scrubbers, canary-token log test, per-env secrets |
| 9 | Scheduler outage → missed posts | Medium | Medium | DB-driven dispatcher (no in-broker ETAs), overdue policy, scheduler-lag alert, ≥2 workers |
| 10 | Media rejected by platforms (specs) | High | Low | Config-driven validation at preview time; clear user errors |
| 11 | LLM caption cost creep / provider outage | Medium | Low | Provider-agnostic interface, per-workspace daily cost cap, cached generations, manual captions always work |
| 12 | Vendor lock-in (Render/R2) | Low | Medium | Docker + S3 API + vanilla Postgres = mechanical migration; exit criteria documented (docs/07 §7) |
| 13 | Compliance gap (data deletion, privacy) | Medium | High | Deletion callback + self-serve deletion tested; retention policies; privacy policy reviewed before each app review |
| 14 | Solo-dev bus factor / burnout | Medium | Medium | Runbooks, ADRs, boring managed infra, mock-first dev keeps scope honest |

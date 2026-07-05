# Phase 7 — Technology Comparison & Recommendations

Method: compare on what *this* project actually stresses — OAuth redirect flows, background jobs, relational job/token data, media handling, small-team operability. Not on generic popularity.

## 1. React (Vite SPA) vs Next.js

| Criterion | React + Vite SPA | Next.js (App Router) |
|---|---|---|
| Dashboard behind login | Excellent | Excellent |
| Marketing/landing + SEO | Poor (CSR) | Excellent (SSR/SSG) |
| OAuth redirect UX | Fine (backend handles it) | Fine + middleware for session gating |
| Ops | Any static host | Vercel first-class |
| Complexity | Lower | Higher (server components mental model) |

**Recommendation: Next.js.** You get the marketing site, docs, and dashboard in one deployable with strong defaults; auth middleware and image optimization are free wins. Trade-off: more framework to learn; if the team wants maximum simplicity, Vite SPA is acceptable — the backend does the heavy lifting either way.

## 2. FastAPI vs Django

| Criterion | FastAPI | Django (+DRF) |
|---|---|---|
| API-first, OpenAPI, async | Native | Bolted on |
| Validation | Pydantic (excellent) | Serializers (verbose) |
| Admin UI | None built-in | Excellent |
| Batteries (auth, ORM) | Choose your own (SQLAlchemy/Alembic) | Included |
| Background jobs | Celery (same) | Celery (same) |

**Recommendation: FastAPI.** This is an API + workers product, not a CMS; Pydantic validation at every boundary is a security feature. Trade-off: you assemble auth/ORM yourself — mitigated by mature libs. Django wins only if you want its admin as an internal ops console; you can add a lightweight admin later instead.

## 3. FastAPI vs NestJS

| Criterion | FastAPI (Python) | NestJS (TypeScript) |
|---|---|---|
| Job ecosystem | Celery (very mature: retries, beat, chords) | BullMQ (good) |
| Type sharing with frontend | No (OpenAPI codegen instead) | Yes (monorepo TS) |
| LLM/AI ecosystem | Strongest | Good |
| Team language | One backend lang (Py) + TS frontend | TS everywhere |

**Recommendation: FastAPI + Celery**, because scheduler/retry maturity is the core of this product and Python's AI ecosystem helps the caption service. NestJS is a legitimate alternative if you strongly prefer one language across the stack — decide once, record an ADR, don't hedge (the PDF's mistake).

## 4. PostgreSQL vs MongoDB

| Criterion | PostgreSQL | MongoDB |
|---|---|---|
| Relational integrity (drafts→targets→jobs, FKs, unique idempotency keys) | Native | Manual |
| Transactions across tables | First-class | Multi-doc supported but not idiomatic |
| Raw API responses | JSONB (indexed) | Native |
| Ops/tooling | Ubiquitous managed options | Fine |

**Recommendation: PostgreSQL — not close.** This domain is relational (users→accounts→posts→jobs) with strict constraints (unique idempotency keys, FK cascades). JSONB gives you Mongo's one advantage anyway.

## 5. Redis vs RabbitMQ (as job broker)

| Criterion | Redis (+Celery) | RabbitMQ (+Celery) |
|---|---|---|
| Ops burden | Trivial (managed, also your cache) | Extra service to run/learn |
| Delivery guarantees | At-least-once with `acks_late`; broker restart can drop in-flight edge cases | Stronger (confirms, DLX) |
| Scale needed here | Hundreds–thousands jobs/day — tiny | Overkill |

**Recommendation: Redis.** One dependency serves broker + cache + rate limits + pub/sub. The delivery-guarantee gap is closed at the application layer by the idempotency design (which you need regardless — even RabbitMQ redelivers). Revisit only at serious scale or strict-ordering needs.

## 6. S3 vs Cloudinary vs Google Cloud Storage

| Criterion | AWS S3 | Cloudinary | GCS |
|---|---|---|---|
| Cost at scale | Low + egress fees | High (transform pricing) | Low + egress fees |
| Egress (platforms fetch your media!) | Paid | Included-ish | Paid |
| Transforms (thumbnail, transcode) | DIY (ffmpeg worker) | Excellent built-in | DIY |
| Lock-in | S3 API = de facto standard | Proprietary | S3-interop partial |

**Recommendation: S3-compatible API with Cloudflare R2 as the default bucket** — zero egress fees matter because Meta/LinkedIn fetch media from you, and the S3 API keeps you portable (dev = MinIO, exit = real S3). Cloudinary is worth adding *later* only if media transformation becomes a product feature; don't pay its margin for storage.

## 7. Hosting: Render vs Railway vs Fly.io vs AWS vs Azure vs GCP

| Criterion | Render | Railway | Fly.io | AWS | Azure | GCP |
|---|---|---|---|---|---|---|
| Managed Postgres+Redis+workers+cron in one | Yes | Yes | Partial (DIY-ish) | Yes (many parts) | Yes (many parts) | Yes (many parts) |
| Ops burden (team of 1–2) | Low | Low | Medium | High | High | High |
| Background workers as first-class | Yes | Yes | Yes | ECS/EKS setup | Setup | Cloud Run jobs |
| Cost predictability | Good | Good | Good | Variable | Variable | Variable |
| Ceiling / enterprise features | Medium | Medium | Medium | Highest | High | High |

**Recommendation: Render for API + workers + beat + managed Postgres/Redis; Vercel for the Next.js frontend.** Rationale: this product's risk is platform-API complexity, not infra scale — spend zero innovation tokens on Kubernetes. Railway is a near-tie (excellent DX; pick it if you prefer its workflow). Fly is great for edge/regions you don't need yet. Move to AWS (ECS Fargate + RDS + ElastiCache + SQS) only when triggered by: >~50k jobs/day, compliance requirements, or VPC-peering needs — the Docker + S3-API + Postgres choices make that migration mechanical.

## Final stack (record as ADR-001)
Next.js on Vercel · FastAPI + Celery on Render · PostgreSQL 16 · Redis 7 · Cloudflare R2 · KMS envelope encryption · Resend · Sentry + OTel · GitHub Actions + Snyk/gitleaks · LLM captions behind provider-agnostic interface.

# Phase 8 — Application Type Analysis

Question: should this be a Claude Artifact, full-stack web app, desktop app, mobile app, or hybrid?

## Scoring matrix (✔ good · ~ workable · ✘ blocking)

| Criterion | Claude Artifact | Full-stack Web | Desktop | Mobile | Hybrid (web+native later) |
|---|---|---|---|---|---|
| Security (secret custody) | ✘ no backend, cannot hold client_secret | ✔ confidential client, KMS | ~ secrets on user machine (public client) | ~ public client | ✔ (web core) |
| OAuth support | ✘ redirect URIs/callbacks not supportable | ✔ standard Authorization Code flow | ~ loopback/device flows; Meta review UX awkward | ~ app-links; token custody on device | ✔ |
| Background jobs & scheduling | ✘ nothing runs when tab closes | ✔ workers + beat run 24/7 | ✘ machine must be on | ✘ OS kills background work | ✔ server does the work |
| Scalability | ✘ | ✔ horizontal workers | ✘ per-machine | ✘ per-device | ✔ |
| Deployment/updates | ✔ trivial but irrelevant | ✔ CI/CD, instant rollback | ~ installers, code signing | ✘ store review cycles | ~ |
| Maintenance | ✘ | ✔ one deployable | ✘ N versions in the wild | ✘ + store policies | ~ |
| Performance | ~ | ✔ | ✔ | ✔ | ✔ |
| Developer experience | ✔ for prototypes | ✔ | ~ | ~ | ~ |
| Long-term growth (teams, billing, more platforms) | ✘ | ✔ | ✘ | ~ companion only | ✔ |

## Analysis in one paragraph each

**Claude Artifact:** cannot hold OAuth client secrets, cannot receive redirect callbacks, and nothing executes when the tab closes — three independent disqualifiers for a *scheduler* whose whole job is acting while the user is away. Verdict: excellent for UI prototyping (mock the Create Post + Status screens to validate UX before writing the real frontend), never for production.

**Full-stack web application:** the only option that satisfies every hard requirement simultaneously: server-side confidential OAuth client, encrypted token custody behind KMS, 24/7 workers for scheduled publishing, webhook receivers (Meta deauth), CI/CD with security gates, and horizontal scaling. It's also what every comparable product (Buffer, Hootsuite, Later) is.

**Desktop application:** distributes your embedded secrets to user machines (a public client), can't reliably run scheduled jobs (laptop closed = post missed), and multiplies support across OS versions. Rejected.

**Mobile application:** same public-client and background-execution problems plus app-store review latency for every fix. Sensible later as a thin *companion* (notifications, approvals, quick edits) over the same API. Rejected as the primary form.

**Hybrid:** correct long-term shape — web app now; the versioned REST API you're already building makes a future mobile companion cheap. Choosing "hybrid" today changes nothing except keeping the API clean, which you should do anyway.

## Recommendation
**Build a full-stack web application** (Next.js + FastAPI per docs/07). Use a throwaway artifact/mock only to validate the dashboard UX in week 1. Revisit a mobile companion after launch when notification-driven approval workflows justify it.

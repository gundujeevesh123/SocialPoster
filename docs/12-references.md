# References — Official Documentation (Deliverable 15)

Re-verify scopes/limits against these before implementing each adapter (rules change monthly).

## Meta / Instagram / Facebook
- Instagram Platform overview: https://developers.facebook.com/docs/instagram-platform
- Instagram content publishing: https://developers.facebook.com/docs/instagram-platform/content-publishing/
- Instagram API with Instagram Login (no FB Page): https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/
- Instagram API with Facebook Login: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login
- Content publishing limit endpoint: https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/content_publishing_limit/
- Pages API getting started: https://developers.facebook.com/docs/pages-api/getting-started/
- Pages API posts: https://developers.facebook.com/docs/pages-api/posts/
- Permissions reference: https://developers.facebook.com/docs/permissions/
- App Review / Advanced Access: https://developers.facebook.com/docs/app-review/
- Data deletion callback: https://developers.facebook.com/docs/development/create-an-app/app-dashboard/data-deletion-callback/
- Webhooks (incl. deauth): https://developers.facebook.com/docs/graph-api/webhooks/

## LinkedIn
- Getting access: https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access
- OAuth 2.0 auth code flow: https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow
- Share on LinkedIn (member posting): https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin
- Posts API (versioned): https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
- API versioning (LinkedIn-Version header): https://learn.microsoft.com/en-us/linkedin/marketing/versioning

## Google / YouTube
- YouTube Data API reference: https://developers.google.com/youtube/v3/docs
- Upload a video guide: https://developers.google.com/youtube/v3/guides/uploading_a_video
- videos.insert: https://developers.google.com/youtube/v3/docs/videos/insert
- Quota calculator: https://developers.google.com/youtube/v3/determine_quota_cost
- Quota & compliance audits: https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits
- OAuth verification: https://support.google.com/cloud/answer/13463073

## Standards & security
- OAuth 2.0 Security Best Current Practice (RFC 9700): https://datatracker.ietf.org/doc/html/rfc9700
- PKCE (RFC 7636): https://datatracker.ietf.org/doc/html/rfc7636
- OWASP ASVS: https://owasp.org/www-project-application-security-verification-standard/
- OWASP Top 10: https://owasp.org/www-project-top-ten/
- Argon2id guidance (OWASP password storage): https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- Snyk CLI/CI docs: https://docs.snyk.io/

## Third-party analyses used to cross-check July-2026 facts (treat as secondary)
- YouTube quota changes (Dec 2025 / Jun 2026): https://www.socialcrawl.dev/blog/youtube-data-api-2026 , https://www.getphyllo.com/post/youtube-api-limits-how-to-calculate-api-usage-cost-and-fix-exceeded-api-quota
- IG publishing limits discussion (conflicting 25/50/100 figures — hence runtime check): https://repostit.io/instagram-graph-api-day-limit/ , https://elfsight.com/blog/instagram-graph-api-complete-developer-guide-for-2026/
- LinkedIn versioning/w_member_social guides: https://zernio.com/blog/linkedin-posting-api , https://connectsafely.ai/articles/linkedin-api-complete-guide-2026

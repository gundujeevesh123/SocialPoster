# GitHub token for Social Poster — exact permissions

The token is pasted into **Settings → GitHub → "GitHub API token"** inside the app.
It is validated against GitHub, encrypted with AES-256-GCM, and stored in the database —
**never put it in a file, never commit it, never paste it in chat.**

## Option A — Fine-grained token (recommended)

github.com → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token

| Setting | Value | Why |
|---|---|---|
| Token name | `social-poster-upload` | identification |
| Expiration | 90 days | limit blast radius; reconnect when it expires |
| Resource owner | your account | repos are created under it |
| Repository access | **All repositories** | required so the token can create the new repo |
| **Repository permissions** | | |
| → Contents | **Read and write** | upload files (blobs, trees, commits, branch update) |
| → Administration | **Read and write** | create the repository itself |
| → Metadata | **Read-only** | mandatory (GitHub adds it automatically) |

Everything else stays "No access". Account permissions: none.

## Option B — Classic token (simpler, broader)

Personal access tokens → **Tokens (classic)** → Generate new token

- Scope: **`repo`** (the single checkbox — covers private repo creation, contents, and pushes)
- Expiration: 90 days

Classic `repo` grants more than the app needs; prefer Option A when possible (least privilege).

## What the app does with it
1. Validates the token (`GET /user`) and stores it encrypted (key never leaves the server).
2. On upload: creates the repo if missing (private by default), then pushes your selected folder
   as one commit via the Git Data API.
3. Filtering is enforced **twice** (browser + server): `.env*` files, `node_modules/`, `.git/`,
   `.next/`, `__pycache__/`, `.venv/`, `data/`, `storage/`, caches, builds, logs, databases and
   files over 5 MB are never uploaded. Hard limits: 400 files / 25 MB per upload.

## Rotation / revocation
Disconnect in Settings (deletes the encrypted copy), then delete the token on GitHub.
To rotate: generate a new token → paste into Settings → old one can be revoked.

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import Base, engine
from .routers import (accounts, auth, events, github, media, misc,
                      notifications, oauth_linkedin, posts)
from .security.middleware import SecurityHeadersMiddleware, install_logging

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    install_logging()
    s = get_settings()
    if s.app_env != "dev":  # fail fast: never boot staging/prod on default secrets
        missing = []
        if not s.token_enc_key_b64:
            missing.append("TOKEN_ENC_KEY_B64")
        if s.session_secret in ("", "dev-only-change-me"):
            missing.append("SESSION_SECRET")
        if missing:
            raise RuntimeError(f"refusing to start ({s.app_env}): weak or missing secrets: {', '.join(missing)}")
    Base.metadata.create_all(engine)   # dev convenience; Alembic when moving to Postgres
    if get_settings().run_worker:
        from .worker.scheduler import start_worker
        start_worker()
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Social Posting Automation API", version="0.1.0",
                  lifespan=lifespan,
                  docs_url="/api/docs" if s.app_env == "dev" else None,
                  openapi_url="/api/openapi.json" if s.app_env == "dev" else None)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CORSMiddleware,
                       allow_origins=[s.web_origin],
                       allow_credentials=True,
                       allow_methods=["*"],
                       allow_headers=["Content-Type", "Idempotency-Key"])
    prefix = "/api/v1"
    for r in (auth.router, media.router, posts.router, oauth_linkedin.router,
              github.router, accounts.router, notifications.router,
              events.router, misc.router):
        app.include_router(r, prefix=prefix)
    return app


app = create_app()

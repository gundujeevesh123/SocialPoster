"""Application settings. Everything secret comes from environment / .env (never committed)."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- app ---
    app_env: str = "dev"                      # dev | staging | prod
    api_base_url: str = "http://localhost:8000"
    web_origin: str = "http://localhost:3000"
    run_worker: bool = True                   # in-process scheduler (dev mode)

    # --- security ---
    session_secret: str = "dev-only-change-me"          # override in .env
    session_max_age_s: int = 60 * 60 * 24 * 7
    token_enc_key_b64: str = ""               # base64 32 bytes; REQUIRED for real OAuth
    token_enc_key_version: int = 1
    min_password_len: int = 10

    # --- database / storage ---
    database_url: str = "sqlite:///./data/app.db"
    storage_dir: str = "./storage"
    max_upload_mb: int = 200

    # --- rate limits (per-process, dev-grade) ---
    login_rate_per_min: int = 5
    api_rate_per_min: int = 120
    publish_rate_per_min: int = 10

    # --- LinkedIn (real) ---
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_redirect_uri: str = "http://localhost:8000/api/v1/oauth/linkedin/callback"
    linkedin_api_version: str = "202506"      # pin; review quarterly
    linkedin_scopes: str = "openid profile email w_member_social"
    enable_linkedin_real: bool = True

    # --- mocked platforms (flags off = mock/demo) ---
    enable_facebook_real: bool = False
    enable_twitter_real: bool = False
    enable_youtube_real: bool = False

    # --- jobs ---
    job_max_attempts: int = 5
    job_base_backoff_s: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()

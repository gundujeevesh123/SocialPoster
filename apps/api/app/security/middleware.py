"""Security headers + request-id + token-redacting log filter."""
import logging
import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware

from ..config import get_settings

_TOKEN_RE = re.compile(
    r"(Bearer\s+[A-Za-z0-9\-._~+/=]{8,}"
    r"|access_token[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9\-._~+/=]{8,}"
    r"|[?&]code=[^&\s\"']{4,})",   # OAuth authorization codes in access logs
    re.IGNORECASE,
)


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            redacted = _TOKEN_RE.sub("[REDACTED_TOKEN]", msg)
            if redacted != msg:
                record.msg, record.args = redacted, ()
        except Exception:
            pass
        return True


def install_logging() -> None:
    root = logging.getLogger()
    if not any(isinstance(f, RedactionFilter) for f in root.filters):
        root.addFilter(RedactionFilter())
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "httpx"):
        lg = logging.getLogger(name)
        if not any(isinstance(f, RedactionFilter) for f in lg.filters):
            lg.addFilter(RedactionFilter())


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.request_id = uuid.uuid4().hex[:16]
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
        if get_settings().app_env != "dev":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

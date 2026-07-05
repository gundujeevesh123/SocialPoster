"""In-memory sliding-window rate limiter (dev-grade; swap for Redis in prod)."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_buckets: dict[str, deque] = defaultdict(deque)


def rate_limit(name: str, limit: int, window_s: int = 60):
    def dependency(request: Request):
        ip = request.client.host if request.client else "unknown"
        key = f"{name}:{ip}"
        now = time.monotonic()
        q = _buckets[key]
        while q and now - q[0] > window_s:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(status_code=429, detail="rate limit exceeded",
                                headers={"Retry-After": str(window_s)})
        q.append(now)
    return dependency

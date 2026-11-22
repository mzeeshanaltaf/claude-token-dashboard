"""Login lockout (in memory) and a CSRF guard middleware.

The lockout lives in process memory on purpose: there is a single backend
container, and a restart clearing the counters is acceptable.
"""
from __future__ import annotations

import json
import threading
import time
from collections import deque
from typing import Callable, Deque, Dict, Hashable, Optional
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

MAX_FAILURES = 5
LOCKOUT_WINDOW = 15 * 60  # seconds
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class LoginLockout:
    """Counts failed logins per key (IP, username) within a sliding window."""

    def __init__(self, max_failures: int = MAX_FAILURES, window: float = LOCKOUT_WINDOW,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.max_failures = max_failures
        self.window = window
        self._clock = clock
        self._fails: Dict[Hashable, Deque[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: Hashable, now: float) -> Optional[Deque[float]]:
        q = self._fails.get(key)
        if q is None:
            return None
        while q and q[0] <= now - self.window:
            q.popleft()
        if not q:
            del self._fails[key]
            return None
        return q

    def retry_after(self, key: Hashable) -> int:
        """Seconds until `key` may try again; 0 when it isn't locked out."""
        with self._lock:
            now = self._clock()
            q = self._prune(key, now)
            if q is None or len(q) < self.max_failures:
                return 0
            # unlocked once enough of the oldest failures have aged out
            oldest_needed = q[len(q) - self.max_failures]
            return max(1, int(oldest_needed + self.window - now) + 1)

    def record_failure(self, key: Hashable) -> None:
        with self._lock:
            now = self._clock()
            q = self._prune(key, now)
            if q is None:
                q = self._fails[key] = deque()
            q.append(now)
            if len(self._fails) > 10_000:  # bound memory under a spray of keys
                for k in list(self._fails):
                    self._prune(k, now)

    def reset(self, key: Hashable) -> None:
        with self._lock:
            self._fails.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._fails.clear()


def _json_error(status: int, detail: str):
    body = json.dumps({"detail": detail}).encode("utf-8")

    async def respond(send: Send) -> None:
        await send({"type": "http.response.start", "status": status, "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ]})
        await send({"type": "http.response.body", "body": body})

    return respond


def _hosts(value: Optional[str]) -> set[str]:
    return {h.strip().lower() for h in (value or "").split(",") if h.strip()}


class CSRFMiddleware:
    """Reject cross-site state changes.

    For every non-GET/HEAD/OPTIONS request:
    - `Content-Type` must be `application/json` (a plain HTML form can't send it,
      and a cross-origin fetch with it needs a CORS preflight we never grant);
    - an `Origin` header, when present, must name the same host as `Host` or
      `X-Forwarded-Host` (the Next.js proxy forwards the public host there).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in SAFE_METHODS:
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        ctype = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if ctype != "application/json":
            await _json_error(415, "Content-Type must be application/json")(send)
            return
        origin = headers.get("origin")
        if origin is not None:
            origin_host = urlsplit(origin).netloc.lower() if origin.lower() != "null" else ""
            allowed = _hosts(headers.get("host")) | _hosts(headers.get("x-forwarded-host"))
            if not origin_host or origin_host not in allowed:
                await _json_error(403, "cross-origin request rejected")(send)
                return
        await self.app(scope, receive, send)

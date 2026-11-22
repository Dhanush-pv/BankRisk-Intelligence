"""Small HTTP wrapper: retries, polite rate limiting, and errors returned instead of raised."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass(frozen=True)
class HttpResponse:
    status_code: int          # 0 means the request never got an HTTP answer
    content: bytes            # body exactly as received (after transport decompression)
    url: str                  # final URL, may contain secrets: always pass through redact_url
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and 200 <= self.status_code < 300


class Client(Protocol):
    def get(self, url: str, params: dict[str, Any] | None = None,
            headers: dict[str, str] | None = None) -> HttpResponse: ...


class HttpClient:
    def __init__(self, min_interval_s: float = 0.0, timeout_s: float = 60.0, retries: int = 3) -> None:
        self._session = requests.Session()
        retry = Retry(total=retries, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=("GET",))
        self._session.mount("https://", HTTPAdapter(max_retries=retry))
        self._min_interval = min_interval_s
        self._timeout = timeout_s
        self._last = 0.0

    def get(self, url: str, params: dict[str, Any] | None = None,
            headers: dict[str, str] | None = None) -> HttpResponse:
        wait = self._min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        try:
            r = self._session.get(url, params=params, headers=headers, timeout=self._timeout)
            return HttpResponse(r.status_code, r.content, r.url)
        except requests.RequestException as exc:
            return HttpResponse(0, b"", url, error=f"{type(exc).__name__}: {exc}")
        finally:
            self._last = time.monotonic()

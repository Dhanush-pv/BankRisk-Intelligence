"""A fake HTTP client so every test runs offline. Responses are hand-made samples, not real API output."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from bankrisk.http import HttpResponse


def json_response(payload: Any, status: int = 200, url: str = "https://example.test") -> HttpResponse:
    return HttpResponse(status, json.dumps(payload).encode("utf-8"), url)


class FakeClient:
    """Routes a request to a handler chosen by URL suffix; records every call."""

    def __init__(self, routes: dict[str, Callable[[dict, dict], HttpResponse]]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, dict, dict]] = []

    def get(self, url, params=None, headers=None) -> HttpResponse:
        params, headers = dict(params or {}), dict(headers or {})
        self.calls.append((url, params, headers))
        for suffix, handler in self.routes.items():
            if url.endswith(suffix):
                resp = handler(params, headers)
                # mimic requests: the final URL includes the query string (and any api_key)
                query = "&".join(f"{k}={v}" for k, v in params.items())
                return HttpResponse(resp.status_code, resp.content, f"{url}?{query}" if query else url,
                                    resp.error)
        return HttpResponse(404, b'{"error":"no route"}', url)


@pytest.fixture()
def config_dir(tmp_path):
    d = tmp_path / "config"
    d.mkdir()
    (d / "banks.yaml").write_text(
        "banks:\n"
        "  - {bank_id: AAA, short_name: Alpha Bank, ticker: AAA, fdic_cert: 100, expected_name_contains: Alpha, sec_cik: 111}\n"
        "  - {bank_id: BBB, short_name: Beta Bank, ticker: BBB, fdic_cert: 200, expected_name_contains: Beta, sec_cik: null}\n",
        encoding="utf-8")
    (d / "fred_series.yaml").write_text(
        'observation_start: "2000-01-01"\nseries:\n'
        "  - {series_id: GOOD, frequency: M, description: ok}\n"
        "  - {series_id: BAD, frequency: D, description: wrong id}\n", encoding="utf-8")
    (d / "fdic_fields.yaml").write_text(
        "max_quarters: 5\nfields: [CERT, REPDTE, ASSET, DEP]\n", encoding="utf-8")
    return d

"""FRED: macro time series (observations plus series metadata), saved untouched."""

from __future__ import annotations

from .config import Series
from .http import Client
from .rawstore import RawWriter, parse_json

BASE = "https://api.stlouisfed.org/fred"


def _error_message(body, response) -> str:
    if isinstance(body, dict) and body.get("error_message"):
        return f"FRED error {body.get('error_code', response.status_code)}: {body['error_message']}"
    return response.error or f"HTTP {response.status_code}"


def fetch_fred(client: Client, writer: RawWriter, series: list[Series], api_key: str,
               observation_start: str) -> None:
    """Download observations and metadata for each series. One failing series does not stop the rest."""
    for s in series:
        obs_url = f"{BASE}/series/observations"
        r = client.get(obs_url, params={"series_id": s.series_id, "api_key": api_key,
                                        "file_type": "json", "observation_start": observation_start})
        body = parse_json(r.content) if r.content else None
        if r.ok and isinstance(body, dict) and isinstance(body.get("observations"), list):
            writer.save(f"{s.series_id}.json", r.content, r.url, r.status_code,
                        record_count=len(body["observations"]))
        else:
            writer.record_error(f"{s.series_id}.json", r.url or obs_url, r.status_code,
                                _error_message(body, r))

        meta_url = f"{BASE}/series"
        m = client.get(meta_url, params={"series_id": s.series_id, "api_key": api_key, "file_type": "json"})
        mbody = parse_json(m.content) if m.content else None
        if m.ok and isinstance(mbody, dict) and isinstance(mbody.get("seriess"), list):
            writer.save(f"{s.series_id}__meta.json", m.content, m.url, m.status_code,
                        record_count=len(mbody["seriess"]))
        else:
            writer.record_error(f"{s.series_id}__meta.json", m.url or meta_url, m.status_code,
                                _error_message(mbody, m))

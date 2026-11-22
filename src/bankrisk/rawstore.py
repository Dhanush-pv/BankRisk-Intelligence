"""Write API responses to disk byte-for-byte and keep a manifest with checksums."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SECRET_PARAMS = {"api_key", "apikey", "key", "token"}


def redact_url(url: str) -> str:
    """Replace secret query parameters with REDACTED so keys never reach disk or the console."""
    parts = urlsplit(url)
    query = [(k, "REDACTED" if k.lower() in SECRET_PARAMS else v) for k, v in parse_qsl(parts.query)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def redact_text(text: str | None) -> str | None:
    if text is None:
        return None
    return re.sub(r"(?i)(api_key|apikey|token)=[^&\s'\"]+", r"\1=REDACTED", text)


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


class RawWriter:
    """Saves files to data/raw/<source>/<run_date>/ and records each in _manifest.json."""

    def __init__(self, base_dir: Path, source: str, run_date: str) -> None:
        self.directory = Path(base_dir) / source / run_date
        self.source = source
        self.run_date = run_date
        self.entries: list[dict[str, Any]] = []

    def save(self, name: str, content: bytes, url: str, status_code: int,
             record_count: int | None = None, note: str | None = None) -> dict[str, Any]:
        self.directory.mkdir(parents=True, exist_ok=True)
        filename = safe_name(name)
        (self.directory / filename).write_bytes(content)
        entry = {
            "file": filename, "url": redact_url(url), "http_status": status_code,
            "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "record_count": record_count, "error": None, "note": note,
        }
        self.entries.append(entry)
        return entry

    def record_error(self, name: str, url: str, status_code: int, error: str) -> dict[str, Any]:
        """Failed request: nothing is written as raw data, but the failure is in the manifest."""
        entry = {
            "file": None, "requested": safe_name(name), "url": redact_url(url),
            "http_status": status_code, "bytes": 0, "sha256": None,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "record_count": None, "error": redact_text(error), "note": None,
        }
        self.entries.append(entry)
        return entry

    def write_manifest(self) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / "_manifest.json"
        payload = {
            "source": self.source, "run_date": self.run_date,
            "files_saved": sum(1 for e in self.entries if e["file"]),
            "errors": sum(1 for e in self.entries if e["error"]),
            "entries": self.entries,
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return path


def parse_json(content: bytes) -> Any | None:
    try:
        return json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

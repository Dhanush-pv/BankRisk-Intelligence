"""Summarise what is in a raw run folder (no network needed)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_fred(folder: Path) -> list[dict[str, Any]]:
    rows = []
    for f in sorted(folder.glob("*.json")):
        if f.name.startswith("_") or f.name.endswith("__meta.json"):
            continue
        obs = _load(f).get("observations", [])
        dates = [o["date"] for o in obs if "date" in o]
        rows.append({"series_id": f.stem, "observations": len(obs),
                     "first_date": min(dates) if dates else None,
                     "last_date": max(dates) if dates else None,
                     "missing_values": sum(1 for o in obs if o.get("value") == ".")})
    return rows


def summarize_fdic(folder: Path) -> list[dict[str, Any]]:
    by_cert: dict[str, list[str]] = {}
    for f in sorted(folder.glob("financials_cert*_p*.json")):
        cert = f.name.split("_")[1].removeprefix("cert")
        for item in _load(f).get("data", []):
            by_cert.setdefault(cert, []).append(str(item.get("data", {}).get("REPDTE", "")))
    return [{"cert": c, "quarters": len(set(d)), "earliest": min(d) if d else None,
             "latest": max(d) if d else None} for c, d in sorted(by_cert.items())]


def summarize_edgar(folder: Path) -> list[dict[str, Any]]:
    rows = []
    for f in sorted(folder.glob("CIK*.json")):
        body = _load(f)
        rows.append({"file": f.name, "entity": body.get("entityName"),
                     "us_gaap_tags": len(body.get("facts", {}).get("us-gaap", {}))})
    return rows


def summarize(raw_dir: Path, run_date: str) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for source, fn in [("fred", summarize_fred), ("fdic", summarize_fdic), ("edgar", summarize_edgar)]:
        folder = Path(raw_dir) / source / run_date
        if folder.exists():
            out[source] = fn(folder)
    return out

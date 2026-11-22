"""FDIC BankFind: institution details and quarterly financials for each bank, saved untouched."""

from __future__ import annotations

from typing import Any

from .config import Bank
from .http import Client
from .rawstore import RawWriter, parse_json

BASE = "https://banks.data.fdic.gov/api"
PAGE_LIMIT = 1000


def _records(body: Any) -> list[dict]:
    """FDIC wraps each record as {"data": {...}, "score": ...}."""
    if not isinstance(body, dict) or not isinstance(body.get("data"), list):
        return []
    return [item.get("data", {}) for item in body["data"] if isinstance(item, dict)]


def fetch_institutions(client: Client, writer: RawWriter, banks: list[Bank]) -> None:
    for bank in banks:
        url = f"{BASE}/institutions"
        r = client.get(url, params={"filters": f"CERT:{bank.fdic_cert}",
                                    "fields": "CERT,NAME,CITY,STALP,ACTIVE,ASSET", "limit": 1,
                                    "format": "json"})
        body = parse_json(r.content) if r.content else None
        name = f"institution_cert{bank.fdic_cert:05d}.json"
        if r.ok and _records(body):
            writer.save(name, r.content, r.url, r.status_code, record_count=len(_records(body)))
        else:
            writer.record_error(name, r.url or url, r.status_code,
                                r.error or f"no institution found for CERT {bank.fdic_cert}")


def fetch_financials(client: Client, writer: RawWriter, banks: list[Bank], fields: list[str],
                     max_quarters: int) -> None:
    """Newest quarters first, paged. Every page is saved as its own raw file."""
    url = f"{BASE}/financials"
    for bank in banks:
        offset, page, collected = 0, 1, 0
        while collected < max_quarters:
            limit = min(PAGE_LIMIT, max_quarters - collected)
            r = client.get(url, params={"filters": f"CERT:{bank.fdic_cert}", "fields": ",".join(fields),
                                        "sort_by": "REPDTE", "sort_order": "DESC",
                                        "limit": limit, "offset": offset, "format": "json"})
            name = f"financials_cert{bank.fdic_cert:05d}_p{page:03d}.json"
            body = parse_json(r.content) if r.content else None
            records = _records(body)
            if not r.ok or body is None:
                writer.record_error(name, r.url or url, r.status_code,
                                    r.error or f"HTTP {r.status_code}")
                break
            writer.save(name, r.content, r.url, r.status_code, record_count=len(records))
            collected += len(records)
            offset += len(records)
            total = (body.get("meta") or {}).get("total")
            if not records or (isinstance(total, int) and offset >= total):
                break
            page += 1


def verify_banks(client: Client, banks: list[Bank], fields: list[str]) -> list[dict[str, Any]]:
    """Check each CERT really belongs to the bank we think it does, and that requested fields exist."""
    results = []
    for bank in banks:
        r = client.get(f"{BASE}/institutions", params={"filters": f"CERT:{bank.fdic_cert}",
                                                       "fields": "CERT,NAME,ACTIVE", "limit": 1,
                                                       "format": "json"})
        recs = _records(parse_json(r.content) if r.content else None)
        if not r.ok:
            results.append({"bank_id": bank.bank_id, "cert": bank.fdic_cert, "status": "error",
                            "detail": r.error or f"HTTP {r.status_code}"})
            continue
        if not recs:
            results.append({"bank_id": bank.bank_id, "cert": bank.fdic_cert, "status": "not_found",
                            "detail": "no institution with this CERT"})
            continue
        returned = str(recs[0].get("NAME", ""))
        match = bank.expected_name_contains.lower() in returned.lower()
        results.append({"bank_id": bank.bank_id, "cert": bank.fdic_cert,
                        "status": "ok" if match else "name_mismatch",
                        "detail": f"FDIC says '{returned}', expected to contain "
                                  f"'{bank.expected_name_contains}'"})
    return results


def check_fields(client: Client, bank: Bank, fields: list[str]) -> list[str]:
    """Return requested fields that the FDIC financials response did not contain."""
    r = client.get(f"{BASE}/financials", params={"filters": f"CERT:{bank.fdic_cert}",
                                                 "fields": ",".join(fields), "sort_by": "REPDTE",
                                                 "sort_order": "DESC", "limit": 1, "format": "json"})
    recs = _records(parse_json(r.content) if r.content else None)
    if not r.ok or not recs:
        raise RuntimeError(r.error or f"could not read a financials record (HTTP {r.status_code})")
    return [f for f in fields if f not in recs[0]]

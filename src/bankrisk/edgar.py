"""SEC EDGAR XBRL company facts for each holding company (optional source)."""

from __future__ import annotations

import time

from .config import Bank
from .http import Client
from .rawstore import RawWriter, parse_json

BASE = "https://data.sec.gov/api/xbrl/companyfacts"


def fetch_company_facts(client: Client, writer: RawWriter, banks: list[Bank], user_agent: str,
                        delay_s: float = 0.2) -> None:
    """SEC requires a User-Agent that identifies you (name and e-mail) and asks for <= 10 requests/second."""
    for bank in banks:
        if bank.sec_cik is None:
            writer.record_error(f"{bank.bank_id}.json", BASE, 0, "no sec_cik configured; skipped")
            continue
        url = f"{BASE}/CIK{bank.sec_cik:010d}.json"
        r = client.get(url, headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
        body = parse_json(r.content) if r.content else None
        name = f"CIK{bank.sec_cik:010d}.json"
        if r.ok and isinstance(body, dict) and isinstance(body.get("facts"), dict):
            writer.save(name, r.content, r.url, r.status_code,
                        record_count=len(body["facts"].get("us-gaap", {})),
                        note=f"entityName={body.get('entityName')}")
        else:
            writer.record_error(name, r.url or url, r.status_code, r.error or f"HTTP {r.status_code}")
        if delay_s:
            time.sleep(delay_s)

"""Command line: verify identifiers, ingest raw data, inspect what was saved."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import edgar, fdic, fred
from .config import ConfigError, Secrets, load_banks, load_fdic, load_fred
from .http import Client, HttpClient
from .inspect_raw import summarize
from .rawstore import RawWriter

ALL_SOURCES = ["fred", "fdic", "edgar"]
DEFAULT_SOURCES = ["fred", "fdic"]


def cmd_verify(args, client: Client | None = None) -> int:
    banks = load_banks(Path(args.config_dir) / "banks.yaml")
    fields = load_fdic(Path(args.config_dir) / "fdic_fields.yaml").fields
    client = client or HttpClient(min_interval_s=0.2)
    problems = 0
    for res in fdic.verify_banks(client, banks, fields):
        print(f"[{res['status'].upper():13}] {res['bank_id']:5} CERT {res['cert']}: {res['detail']}")
        problems += res["status"] != "ok"
    try:
        missing = fdic.check_fields(client, banks[0], fields)
        if missing:
            print(f"[FIELDS       ] requested but not returned by FDIC: {missing}")
            problems += 1
        else:
            print("[FIELDS       ] all requested FDIC fields are returned")
    except RuntimeError as exc:
        print(f"[FIELDS       ] could not check fields: {exc}")
        problems += 1
    print("Verification passed." if not problems else f"{problems} problem(s): fix config/ before ingesting.")
    return 1 if problems else 0


def cmd_ingest(args, client: Client | None = None) -> int:
    cfg = Path(args.config_dir)
    banks = load_banks(cfg / "banks.yaml")
    secrets = Secrets.from_env(args.env_file)
    client = client or HttpClient(min_interval_s=0.2)
    raw_dir = Path(args.raw_dir)
    errors = 0

    for source in args.sources:
        writer = RawWriter(raw_dir, source, args.date)
        if source == "fred":
            if not secrets.fred_api_key:
                print("FRED skipped: set FRED_API_KEY in .env (free key: https://fred.stlouisfed.org/docs/api/api_key.html)")
                errors += 1
                continue
            conf = load_fred(cfg / "fred_series.yaml")
            fred.fetch_fred(client, writer, conf.series, secrets.fred_api_key, conf.observation_start)
        elif source == "fdic":
            conf = load_fdic(cfg / "fdic_fields.yaml")
            fdic.fetch_institutions(client, writer, banks)
            fdic.fetch_financials(client, writer, banks, conf.fields, args.max_quarters or conf.max_quarters)
        elif source == "edgar":
            if not secrets.sec_user_agent:
                print("EDGAR skipped: set SEC_USER_AGENT in .env, e.g. 'Your Name your@email.com'")
                errors += 1
                continue
            edgar.fetch_company_facts(client, writer, banks, secrets.sec_user_agent)
        manifest = writer.write_manifest()
        saved = sum(1 for e in writer.entries if e["file"])
        failed = [e for e in writer.entries if e["error"]]
        errors += len(failed)
        print(f"{source}: {saved} file(s) saved, {len(failed)} failed -> {manifest}")
        for e in failed:
            print(f"   FAILED {e.get('requested') or e['file']}: {e['error']}")
    return 1 if errors else 0


def cmd_inspect(args) -> int:
    summary = summarize(Path(args.raw_dir), args.date)
    if not summary:
        print(f"No raw data found for {args.date} under {args.raw_dir}")
        return 1
    print(json.dumps(summary, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bankrisk", description="BankRisk Intelligence: raw ingestion")
    p.add_argument("--config-dir", default="config")
    p.add_argument("--raw-dir", default="data/raw")
    p.add_argument("--env-file", default=".env")
    p.add_argument("--date", default=date.today().isoformat(), help="run date YYYY-MM-DD")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("verify", help="check bank identifiers and FDIC fields against the live FDIC API")
    ing = sub.add_parser("ingest", help="download raw data")
    ing.add_argument("--sources", nargs="+", choices=ALL_SOURCES, default=DEFAULT_SOURCES)
    ing.add_argument("--max-quarters", type=int, default=None, help="override fdic_fields.yaml")
    sub.add_parser("inspect", help="summarise saved raw files")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        code = {"verify": cmd_verify, "ingest": cmd_ingest, "inspect": cmd_inspect}[args.command](args)
    except (ConfigError, FileNotFoundError) as exc:
        sys.exit(f"Configuration problem: {exc}")
    sys.exit(code)


if __name__ == "__main__":
    main()

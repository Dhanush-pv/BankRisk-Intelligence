# Changelog

**Project author:** Dhanush

## Week 1 - Raw ingestion

- Bank universe of 15 US bank holding companies with FDIC CERT and SEC CIK identifiers (`config/banks.yaml`).
- FRED ingestion: 11 macro series (daily, monthly and quarterly) plus series metadata.
- FDIC BankFind ingestion: institution record and up to 80 quarters of financials per bank, paged.
- Optional SEC EDGAR XBRL company-facts ingestion.
- Raw responses saved byte-for-byte under `data/raw/<source>/<date>/` with a `_manifest.json` (SHA-256, size,
  status, record count). API keys are redacted from everything written to disk.
- `verify` command checks the identifiers and requested FDIC fields against the live FDIC API.
- `inspect` command summarises saved raw files.
- Offline test suite with a fake HTTP client.

## Week 1 - review fixes

- Fixed Python 3.10 compatibility: `datetime.UTC` (3.11+) replaced with `timezone.utc`.
- `config/banks.yaml`: M&T's FDIC legal name is 'Manufacturers and Traders Trust Company'; name check updated.
- Documented that global CLI options (`--date`, `--raw-dir`, ...) go before the command.
- Added tests for `main()` exit codes and for the `--date` option position.

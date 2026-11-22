# BankRisk Intelligence 

**Author:** Dhanush

## What gets downloaded

| Source | What | Why it matters | Needs |
|---|---|---|---|
| **FRED** (St. Louis Fed) | 11 macro series: interest rates, yield-curve spreads, inflation, unemployment, GDP, delinquency rates. Daily, monthly and quarterly | The macro join across different frequencies is a key part of the project | Free API key |
| **FDIC BankFind** | Up to 80 quarters of financials for each bank (assets, deposits, loans, capital ratios, ...) | The core bank metrics | Nothing |
| **SEC EDGAR** (optional) | XBRL "company facts" for each holding company | A second source to reconcile against FDIC | Your name and e-mail in a header |

Bank universe: 15 large US bank holding companies (`config/banks.yaml`). **FDIC reports the bank
subsidiary, SEC filings are made by the holding company**, so the two will not match exactly. 

## Step-by-step setup (beginner friendly)

1. **Install Python 3.10 or newer** (developed and tested on 3.12) and Git.
2. **Open a terminal in this folder** and create a virtual environment:
   ```bash
   python -m venv .venv
   # Windows PowerShell:   .venv\Scripts\Activate.ps1
   # macOS / Linux:        source .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -e ".[dev]"
   ```
3. **Create your settings file:** copy `.env.example` to `.env` (`copy` on Windows, `cp` on macOS/Linux).
4. **Get a free FRED API key:** create an account at fred.stlouisfed.org, then request a key at
   https://fred.stlouisfed.org/docs/api/api_key.html. Paste it after `FRED_API_KEY=` in `.env`.
   Never commit `.env` (it is already in `.gitignore`).
5. *(Optional, for EDGAR)* In `.env`, set `SEC_USER_AGENT=Your Name your@email.com`. SEC requires this.

## Run it

```bash
pytest -q                                   # offline tests; no internet or key needed
python -m bankrisk.cli verify               # 1. check bank identifiers against the live FDIC API
python -m bankrisk.cli ingest               # 2. download FRED + FDIC (default)
python -m bankrisk.cli ingest --sources edgar     # 3. optional: EDGAR
python -m bankrisk.cli inspect              # 4. summarise what was saved
```

**Always run `verify` first.** The FDIC certificate numbers, FRED series ids and FDIC field names in
`config/` were written from memory and have not been checked against the live APIs in this package.
`verify` tells you which bank identifiers are wrong or missing. During `ingest`, a wrong FRED series id is
recorded as a failed entry in the manifest and the run continues; the failure is printed at the end and
the command exits with an error code.

Useful options: `--max-quarters 40` (after `ingest`) and the global options `--date`, `--raw-dir`, `--config-dir`,
`--env-file`. **Global options go before the command**, e.g. `python -m bankrisk.cli --date 2026-11-20 ingest`.

## Where the output goes

```text
data/raw/
├── fred/<run date>/    DGS10.json, DGS10__meta.json, ... , _manifest.json
├── fdic/<run date>/    institution_cert00628.json, financials_cert00628_p001.json, ... , _manifest.json
└── edgar/<run date>/   CIK0000019617.json, ... , _manifest.json
```


"""Typed loading and validation of the YAML configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised when a configuration file is malformed."""


@dataclass(frozen=True)
class Bank:
    bank_id: str
    short_name: str
    ticker: str
    fdic_cert: int
    expected_name_contains: str
    sec_cik: int | None


@dataclass(frozen=True)
class Series:
    series_id: str
    frequency: str
    description: str


@dataclass(frozen=True)
class FredConfig:
    observation_start: str
    series: list[Series]


@dataclass(frozen=True)
class FdicConfig:
    max_quarters: int
    fields: list[str]


def _load_yaml(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a mapping at the top level")
    return data


def load_banks(path: Path) -> list[Bank]:
    raw = _load_yaml(path).get("banks")
    if not raw:
        raise ConfigError(f"{path}: no banks defined")
    banks = []
    for item in raw:
        try:
            cik = item.get("sec_cik")
            banks.append(Bank(
                bank_id=str(item["bank_id"]), short_name=str(item["short_name"]),
                ticker=str(item.get("ticker", "")), fdic_cert=int(item["fdic_cert"]),
                expected_name_contains=str(item["expected_name_contains"]),
                sec_cik=int(cik) if cik is not None else None))
        except (KeyError, TypeError, ValueError) as exc:
            raise ConfigError(f"{path}: invalid bank entry {item!r}: {exc}") from exc
    for label, values in [("bank_id", [b.bank_id for b in banks]),
                          ("fdic_cert", [b.fdic_cert for b in banks])]:
        dupes = sorted({v for v in values if values.count(v) > 1}, key=str)
        if dupes:
            raise ConfigError(f"{path}: duplicate {label}: {dupes}")
    return banks


def load_fred(path: Path) -> FredConfig:
    data = _load_yaml(path)
    series = [Series(str(s["series_id"]), str(s["frequency"]), str(s.get("description", "")))
              for s in data.get("series", [])]
    if not series:
        raise ConfigError(f"{path}: no series defined")
    ids = [s.series_id for s in series]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ConfigError(f"{path}: duplicate series ids {dupes}")
    bad = [s.series_id for s in series if s.frequency not in {"D", "W", "M", "Q", "A"}]
    if bad:
        raise ConfigError(f"{path}: invalid frequency for {bad}")
    return FredConfig(str(data.get("observation_start", "2000-01-01")), series)


def load_fdic(path: Path) -> FdicConfig:
    data = _load_yaml(path)
    fields = [str(f) for f in data.get("fields", [])]
    if "CERT" not in fields or "REPDTE" not in fields:
        raise ConfigError(f"{path}: fields must include CERT and REPDTE")
    return FdicConfig(int(data.get("max_quarters", 80)), fields)


@dataclass(frozen=True)
class Secrets:
    fred_api_key: str | None
    sec_user_agent: str | None

    @classmethod
    def from_env(cls, env_file: str | Path = ".env") -> Secrets:
        load_dotenv(env_file)
        return cls(os.getenv("FRED_API_KEY") or None, os.getenv("SEC_USER_AGENT") or None)

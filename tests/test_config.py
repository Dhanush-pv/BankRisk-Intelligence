from pathlib import Path

import pytest

from bankrisk.config import ConfigError, load_banks, load_fdic, load_fred

REPO_CONFIG = Path("config")


def test_repo_configs_are_valid():
    banks = load_banks(REPO_CONFIG / "banks.yaml")
    assert 10 <= len(banks) <= 16
    assert load_fred(REPO_CONFIG / "fred_series.yaml").series
    fields = load_fdic(REPO_CONFIG / "fdic_fields.yaml").fields
    assert "CERT" in fields and "REPDTE" in fields


def test_repo_fred_series_cover_daily_monthly_quarterly():
    freqs = {s.frequency for s in load_fred(REPO_CONFIG / "fred_series.yaml").series}
    assert {"D", "M", "Q"} <= freqs


def test_duplicate_cert_rejected(tmp_path):
    p = tmp_path / "banks.yaml"
    p.write_text("banks:\n"
                 "  - {bank_id: A, short_name: a, fdic_cert: 1, expected_name_contains: a}\n"
                 "  - {bank_id: B, short_name: b, fdic_cert: 1, expected_name_contains: b}\n")
    with pytest.raises(ConfigError, match="duplicate fdic_cert"):
        load_banks(p)


def test_missing_field_rejected(tmp_path):
    p = tmp_path / "banks.yaml"
    p.write_text("banks:\n  - {bank_id: A, short_name: a}\n")
    with pytest.raises(ConfigError, match="invalid bank entry"):
        load_banks(p)


def test_fdic_fields_must_include_keys(tmp_path):
    p = tmp_path / "f.yaml"
    p.write_text("fields: [ASSET]\n")
    with pytest.raises(ConfigError):
        load_fdic(p)


def test_bad_frequency_rejected(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text("series:\n  - {series_id: X, frequency: Z}\n")
    with pytest.raises(ConfigError, match="invalid frequency"):
        load_fred(p)

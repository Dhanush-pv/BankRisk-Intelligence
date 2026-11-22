import json

from conftest import FakeClient, json_response

from bankrisk import edgar, fdic, fred
from bankrisk.config import load_banks, load_fred
from bankrisk.inspect_raw import summarize
from bankrisk.rawstore import RawWriter


def test_fred_saves_good_series_and_records_bad_one(tmp_path, config_dir):
    series = load_fred(config_dir / "fred_series.yaml").series

    def observations(params, _):
        if params["series_id"] == "BAD":
            return json_response({"error_code": 400, "error_message": "Bad Request. The series does not exist."}, 400)
        return json_response({"observations": [{"date": "2020-01-01", "value": "1.5"},
                                               {"date": "2020-02-01", "value": "."}]})

    def meta(params, _):
        if params["series_id"] == "BAD":
            return json_response({"error_code": 400, "error_message": "nope"}, 400)
        return json_response({"seriess": [{"id": params["series_id"], "units": "Percent"}]})

    client = FakeClient({"/series/observations": observations, "/series": meta})
    w = RawWriter(tmp_path, "fred", "2026-11-20")
    fred.fetch_fred(client, w, series, "SECRETKEY", "2000-01-01")
    manifest = json.loads(w.write_manifest().read_text())
    names = {e["file"] for e in manifest["entries"] if e["file"]}
    assert names == {"GOOD.json", "GOOD__meta.json"}
    errors = [e for e in manifest["entries"] if e["error"]]
    assert len(errors) == 2 and "does not exist" in errors[0]["error"]
    assert "SECRETKEY" not in json.dumps(manifest)
    # the observation request carried the start date and the key
    assert client.calls[0][1]["observation_start"] == "2000-01-01"


def test_fred_rejects_unexpected_json(tmp_path, config_dir):
    series = load_fred(config_dir / "fred_series.yaml").series[:1]
    client = FakeClient({"/series/observations": lambda p, h: json_response({"unexpected": 1}),
                         "/series": lambda p, h: json_response({"unexpected": 1})})
    w = RawWriter(tmp_path, "fred", "d")
    fred.fetch_fred(client, w, series, "K", "2000-01-01")
    assert not any(e["file"] for e in w.entries) and all(e["error"] for e in w.entries)


def _fdic_page(total, start, count, cert=100):
    data = [{"data": {"CERT": cert, "REPDTE": str(20260331 - 10000 * (start + i)), "ASSET": 1, "DEP": 1},
             "score": 1} for i in range(count)]
    return json_response({"meta": {"total": total}, "data": data})


def test_fdic_financials_paginates_and_respects_max_quarters(tmp_path, config_dir, monkeypatch):
    monkeypatch.setattr(fdic, "PAGE_LIMIT", 2)
    banks = load_banks(config_dir / "banks.yaml")[:1]

    def financials(params, _):
        offset, limit = int(params["offset"]), int(params["limit"])
        return _fdic_page(total=10, start=offset, count=limit)

    client = FakeClient({"/financials": financials})
    w = RawWriter(tmp_path, "fdic", "d")
    fdic.fetch_financials(client, w, banks, ["CERT", "REPDTE", "ASSET", "DEP"], max_quarters=5)
    files = [e["file"] for e in w.entries if e["file"]]
    assert files == ["financials_cert00100_p001.json", "financials_cert00100_p002.json",
                     "financials_cert00100_p003.json"]
    assert sum(e["record_count"] for e in w.entries) == 5       # stopped at max_quarters
    assert client.calls[0][1]["sort_by"] == "REPDTE" and client.calls[0][1]["sort_order"] == "DESC"
    assert client.calls[0][1]["filters"] == "CERT:100"


def test_fdic_stops_when_total_reached(tmp_path, config_dir):
    banks = load_banks(config_dir / "banks.yaml")[:1]
    client = FakeClient({"/financials": lambda p, h: _fdic_page(total=3, start=0, count=3)})
    w = RawWriter(tmp_path, "fdic", "d")
    fdic.fetch_financials(client, w, banks, ["CERT", "REPDTE"], max_quarters=80)
    assert len(client.calls) == 1


def test_fdic_http_error_recorded_not_raised(tmp_path, config_dir):
    banks = load_banks(config_dir / "banks.yaml")
    client = FakeClient({"/financials": lambda p, h: json_response({"message": "boom"}, 500)})
    w = RawWriter(tmp_path, "fdic", "d")
    fdic.fetch_financials(client, w, banks, ["CERT", "REPDTE"], 5)
    assert len([e for e in w.entries if e["error"]]) == 2        # one per bank, loop continued


def test_verify_banks_detects_mismatch_and_missing(config_dir):
    banks = load_banks(config_dir / "banks.yaml")

    def institutions(params, _):
        cert = params["filters"].split(":")[1]
        if cert == "100":
            return json_response({"data": [{"data": {"CERT": 100, "NAME": "Alpha Bank, N.A."}}]})
        return json_response({"data": []})

    res = fdic.verify_banks(FakeClient({"/institutions": institutions}), banks, ["CERT"])
    assert res[0]["status"] == "ok" and res[1]["status"] == "not_found"

    def wrong(params, _):
        return json_response({"data": [{"data": {"NAME": "Totally Different Bank"}}]})

    res = fdic.verify_banks(FakeClient({"/institutions": wrong}), banks[:1], ["CERT"])
    assert res[0]["status"] == "name_mismatch"


def test_check_fields_reports_missing(config_dir):
    banks = load_banks(config_dir / "banks.yaml")
    client = FakeClient({"/financials": lambda p, h: json_response(
        {"data": [{"data": {"CERT": 1, "REPDTE": "20260331", "ASSET": 5}}]})})
    assert fdic.check_fields(client, banks[0], ["CERT", "REPDTE", "ASSET", "DEP"]) == ["DEP"]


def test_edgar_sends_user_agent_and_skips_banks_without_cik(tmp_path, config_dir):
    banks = load_banks(config_dir / "banks.yaml")
    facts = {"entityName": "Alpha Corp", "facts": {"us-gaap": {"Assets": {}, "Deposits": {}}}}
    client = FakeClient({".json": lambda p, h: json_response(facts)})
    w = RawWriter(tmp_path, "edgar", "d")
    edgar.fetch_company_facts(client, w, banks, "Test User test@example.com", delay_s=0)
    assert client.calls[0][2]["User-Agent"] == "Test User test@example.com"
    assert client.calls[0][0].endswith("CIK0000000111.json")
    assert [e["file"] for e in w.entries if e["file"]] == ["CIK0000000111.json"]
    assert w.entries[0]["record_count"] == 2
    assert any("no sec_cik" in (e["error"] or "") for e in w.entries)


def test_inspect_summaries(tmp_path):
    fred_dir = tmp_path / "fred" / "d"
    fred_dir.mkdir(parents=True)
    (fred_dir / "X.json").write_text(json.dumps(
        {"observations": [{"date": "2020-01-01", "value": "1"}, {"date": "2020-02-01", "value": "."}]}))
    (fred_dir / "X__meta.json").write_text("{}")
    (fred_dir / "_manifest.json").write_text("{}")
    fdic_dir = tmp_path / "fdic" / "d"
    fdic_dir.mkdir(parents=True)
    (fdic_dir / "financials_cert00100_p001.json").write_text(json.dumps(
        {"data": [{"data": {"REPDTE": "20260331"}}, {"data": {"REPDTE": "20251231"}}]}))
    s = summarize(tmp_path, "d")
    assert s["fred"] == [{"series_id": "X", "observations": 2, "first_date": "2020-01-01",
                          "last_date": "2020-02-01", "missing_values": 1}]
    assert s["fdic"] == [{"cert": "00100", "quarters": 2, "earliest": "20251231", "latest": "20260331"}]
    assert "edgar" not in s

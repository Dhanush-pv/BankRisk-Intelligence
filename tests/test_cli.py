import json

from conftest import FakeClient, json_response

from bankrisk import cli


def _args(config_dir, tmp_path, **kw):
    p = cli.build_parser()
    argv = ["--config-dir", str(config_dir), "--raw-dir", str(tmp_path / "raw"),
            "--env-file", str(tmp_path / "none.env"), "--date", "2026-11-20", *kw.pop("argv")]
    return p.parse_args(argv)


def test_ingest_without_fred_key_reports_and_fails(config_dir, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    args = _args(config_dir, tmp_path, argv=["ingest", "--sources", "fred"])
    code = cli.cmd_ingest(args, client=FakeClient({}))
    assert code == 1 and "FRED_API_KEY" in capsys.readouterr().out


def test_ingest_fdic_end_to_end(config_dir, tmp_path, monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    inst = lambda p, h: json_response({"data": [{"data": {"CERT": 1, "NAME": "Alpha Bank"}}]})
    fin = lambda p, h: json_response({"meta": {"total": 1}, "data": [{"data": {"CERT": 1, "REPDTE": "20260331"}}]})
    client = FakeClient({"/institutions": inst, "/financials": fin})
    args = _args(config_dir, tmp_path, argv=["ingest", "--sources", "fdic"])
    assert cli.cmd_ingest(args, client=client) == 0
    manifest = json.loads((tmp_path / "raw" / "fdic" / "2026-11-20" / "_manifest.json").read_text())
    assert manifest["files_saved"] == 4 and manifest["errors"] == 0     # 2 banks x (institution + 1 page)


def test_ingest_edgar_needs_user_agent(config_dir, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    args = _args(config_dir, tmp_path, argv=["ingest", "--sources", "edgar"])
    assert cli.cmd_ingest(args, client=FakeClient({})) == 1
    assert "SEC_USER_AGENT" in capsys.readouterr().out


def test_verify_exit_code(config_dir, tmp_path):
    def institutions(params, _):
        return json_response({"data": [{"data": {"NAME": "Alpha Bank" if "100" in params["filters"] else "Beta Bank"}}]})
    fin = lambda p, h: json_response({"data": [{"data": {"CERT": 1, "REPDTE": "x", "ASSET": 1, "DEP": 1}}]})
    args = _args(config_dir, tmp_path, argv=["verify"])
    assert cli.cmd_verify(args, client=FakeClient({"/institutions": institutions, "/financials": fin})) == 0
    bad = FakeClient({"/institutions": lambda p, h: json_response({"data": []}), "/financials": fin})
    assert cli.cmd_verify(args, client=bad) == 1


def test_inspect_without_data(config_dir, tmp_path):
    args = _args(config_dir, tmp_path, argv=["inspect"])
    assert cli.cmd_inspect(args) == 1


def test_main_exits_nonzero_on_missing_config(tmp_path):
    import pytest
    with pytest.raises(SystemExit) as exc:
        cli.main(["--config-dir", str(tmp_path / "missing"), "verify"])
    assert exc.value.code != 0


def test_date_option_must_precede_command():
    import pytest
    args = cli.build_parser().parse_args(["--date", "2026-01-02", "ingest"])
    assert args.date == "2026-01-02"
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["ingest", "--date", "2026-01-02"])

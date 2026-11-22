import hashlib
import json

from bankrisk.rawstore import RawWriter, redact_text, redact_url


def test_redact_url_hides_api_key():
    url = "https://api.stlouisfed.org/fred/series?series_id=X&api_key=SECRET123&file_type=json"
    out = redact_url(url)
    assert "SECRET123" not in out and "api_key=REDACTED" in out and "series_id=X" in out


def test_redact_text():
    assert "SECRET" not in redact_text("failed: ...?api_key=SECRET&x=1")
    assert redact_text(None) is None


def test_raw_bytes_saved_untouched_with_checksum(tmp_path):
    w = RawWriter(tmp_path, "fred", "2026-11-20")
    content = b'{"b": 1,\n  "a":   [1,2] }'          # odd spacing must survive unchanged
    e = w.save("S.json", content, "https://x.test/p?api_key=K", 200, record_count=2)
    saved = (tmp_path / "fred" / "2026-11-20" / "S.json").read_bytes()
    assert saved == content
    assert e["sha256"] == hashlib.sha256(content).hexdigest()
    assert "K" not in e["url"].replace("REDACTED", "")


def test_manifest_counts_and_no_secret(tmp_path):
    w = RawWriter(tmp_path, "fred", "2026-11-20")
    w.save("a.json", b"{}", "https://x.test?api_key=K1", 200)
    w.record_error("b.json", "https://x.test?api_key=K2", 400, "bad request api_key=K2")
    path = w.write_manifest()
    text = path.read_text()
    payload = json.loads(text)
    assert payload["files_saved"] == 1 and payload["errors"] == 1
    assert "K1" not in text and "K2" not in text


def test_unsafe_names_are_sanitised(tmp_path):
    w = RawWriter(tmp_path, "fdic", "d")
    w.save("../evil/name.json", b"{}", "https://x.test", 200)
    assert [f.name for f in (tmp_path / "fdic" / "d").iterdir()] == [".._evil_name.json"]
    assert not (tmp_path / "evil").exists()

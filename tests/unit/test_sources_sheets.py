"""Google Sheets adapter plumbing — hermetic, no network.

httpx.get is monkeypatched (as imported in the adapter module) to return a
fake response. Covers the full error taxonomy in
spec/capabilities/data-sources.md.
"""
import httpx
import pytest

from domain.sources import SourceError
from domain.sources import sheets


class FakeResponse:
    def __init__(self, status_code=200, content=b"", content_type="text/csv"):
        self.status_code = status_code
        self.content = content
        self.headers = {"content-type": content_type}

    def json(self):  # not used by the sheets adapter, present for parity
        import json

        return json.loads(self.content.decode())


def _patch_get(monkeypatch, resp=None, raise_exc=None):
    def _fake_get(url, *args, **kwargs):
        if raise_exc is not None:
            raise raise_exc
        return resp

    monkeypatch.setattr(sheets.httpx, "get", _fake_get)


# --- extract_sheet_id_and_gid -------------------------------------------------

def test_extract_valid_edit_url_with_gid():
    url = "https://docs.google.com/spreadsheets/d/ABC123-_/edit#gid=42"
    sid, gid = sheets.extract_sheet_id_and_gid(url)
    assert sid == "ABC123-_"
    assert gid == "42"


def test_extract_url_without_gid_defaults_zero():
    url = "https://docs.google.com/spreadsheets/d/ABC123/edit"
    sid, gid = sheets.extract_sheet_id_and_gid(url)
    assert sid == "ABC123"
    assert gid == "0"


def test_extract_blank_url_invalid():
    with pytest.raises(SourceError) as ei:
        sheets.extract_sheet_id_and_gid("   ")
    assert ei.value.code == "INVALID_SHEET_URL"
    assert ei.value.status == 400


def test_extract_non_sheets_url_invalid():
    with pytest.raises(SourceError) as ei:
        sheets.extract_sheet_id_and_gid("https://example.com/foo/bar")
    assert ei.value.code == "INVALID_SHEET_URL"
    assert ei.value.status == 400


# --- build_export_url ---------------------------------------------------------

def test_build_export_url_shape():
    out = sheets.build_export_url("SID", "7")
    assert "format=csv" in out
    assert "gid=7" in out
    assert "/spreadsheets/d/SID/export" in out


# --- fetch_google_sheet -------------------------------------------------------

_EDIT_URL = "https://docs.google.com/spreadsheets/d/SHEET_ID_123/edit#gid=0"


def test_fetch_happy_path(monkeypatch):
    csv = b"region,revenue\nnorth,10\nsouth,20\n"
    _patch_get(monkeypatch, FakeResponse(200, csv, "text/csv"))
    df, title = sheets.fetch_google_sheet(_EDIT_URL)
    assert df.shape[0] == 2
    assert list(df.columns) == ["region", "revenue"]
    assert isinstance(title, str) and title


def test_fetch_html_content_type_not_accessible(monkeypatch):
    _patch_get(monkeypatch, FakeResponse(200, b"login form", "text/html"))
    with pytest.raises(SourceError) as ei:
        sheets.fetch_google_sheet(_EDIT_URL)
    assert ei.value.code == "SHEET_NOT_ACCESSIBLE"
    assert ei.value.status == 400


def test_fetch_html_body_not_accessible(monkeypatch):
    _patch_get(monkeypatch, FakeResponse(200, b"<!DOCTYPE html><html></html>", "text/plain"))
    with pytest.raises(SourceError) as ei:
        sheets.fetch_google_sheet(_EDIT_URL)
    assert ei.value.code == "SHEET_NOT_ACCESSIBLE"
    assert ei.value.status == 400


def test_fetch_non_200_status(monkeypatch):
    _patch_get(monkeypatch, FakeResponse(404, b"", "text/csv"))
    with pytest.raises(SourceError) as ei:
        sheets.fetch_google_sheet(_EDIT_URL)
    assert ei.value.code == "FETCH_FAILED"
    assert ei.value.status == 502


def test_fetch_timeout(monkeypatch):
    _patch_get(monkeypatch, raise_exc=httpx.TimeoutException("timed out"))
    with pytest.raises(SourceError) as ei:
        sheets.fetch_google_sheet(_EDIT_URL)
    assert ei.value.code == "FETCH_FAILED"
    assert ei.value.status == 502


def test_fetch_http_error(monkeypatch):
    _patch_get(monkeypatch, raise_exc=httpx.HTTPError("boom"))
    with pytest.raises(SourceError) as ei:
        sheets.fetch_google_sheet(_EDIT_URL)
    assert ei.value.code == "FETCH_FAILED"
    assert ei.value.status == 502


def test_fetch_file_too_large(monkeypatch):
    monkeypatch.setenv("AGENT_MAX_UPLOAD_MB", "0")
    _patch_get(monkeypatch, FakeResponse(200, b"region,revenue\nnorth,10\n", "text/csv"))
    with pytest.raises(SourceError) as ei:
        sheets.fetch_google_sheet(_EDIT_URL)
    assert ei.value.code == "FILE_TOO_LARGE"
    assert ei.value.status == 413


def test_fetch_empty_csv_parse_failed(monkeypatch):
    _patch_get(monkeypatch, FakeResponse(200, b"", "text/csv"))
    with pytest.raises(SourceError) as ei:
        sheets.fetch_google_sheet(_EDIT_URL)
    assert ei.value.code == "PARSE_FAILED"
    assert ei.value.status == 400


def test_fetch_headers_only_no_rows_parse_failed(monkeypatch):
    _patch_get(monkeypatch, FakeResponse(200, b"a,b,c\n", "text/csv"))
    with pytest.raises(SourceError) as ei:
        sheets.fetch_google_sheet(_EDIT_URL)
    assert ei.value.code == "PARSE_FAILED"
    assert ei.value.status == 400

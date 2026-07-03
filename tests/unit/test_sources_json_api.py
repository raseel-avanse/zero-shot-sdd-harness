"""JSON-API adapter plumbing — hermetic, no network.

httpx.get is monkeypatched (as imported in the adapter module) to return a
fake response. Covers the four normalization rules + the full error taxonomy in
spec/capabilities/data-sources.md.
"""
import httpx
import pytest

from domain.sources import SourceError
from domain.sources import json_api


class FakeResponse:
    def __init__(self, status_code=200, payload=None, content=None, raise_json=False):
        self.status_code = status_code
        self._payload = payload
        self._raise_json = raise_json
        if content is not None:
            self.content = content
        else:
            import json

            self.content = json.dumps(payload if payload is not None else {}).encode()
        self.headers = {"content-type": "application/json"}

    def json(self):
        if self._raise_json:
            raise ValueError("not valid json")
        return self._payload


def _patch_get(monkeypatch, resp=None, raise_exc=None):
    def _fake_get(url, *args, **kwargs):
        if raise_exc is not None:
            raise raise_exc
        return resp

    monkeypatch.setattr(json_api.httpx, "get", _fake_get)


_URL = "https://api.example.com/data"


# --- _validate_url / URL guarding --------------------------------------------

def test_blank_url_invalid():
    with pytest.raises(SourceError) as ei:
        json_api.fetch_json_api("   ")
    assert ei.value.code == "INVALID_URL"
    assert ei.value.status == 400


def test_non_http_scheme_invalid():
    with pytest.raises(SourceError) as ei:
        json_api.fetch_json_api("ftp://example.com/data.json")
    assert ei.value.code == "INVALID_URL"
    assert ei.value.status == 400


# --- Rule 1: explicit records_path -------------------------------------------

def test_rule1_nested_records_path(monkeypatch):
    payload = {"data": {"items": [{"a": 1}, {"a": 2}, {"a": 3}]}}
    _patch_get(monkeypatch, FakeResponse(200, payload))
    df, title = json_api.fetch_json_api(_URL, records_path="data.items")
    assert df.shape[0] == 3
    assert list(df.columns) == ["a"]
    assert isinstance(title, str) and title


def test_rule1_missing_key_no_tabular_data(monkeypatch):
    payload = {"data": {"items": [{"a": 1}]}}
    _patch_get(monkeypatch, FakeResponse(200, payload))
    with pytest.raises(SourceError) as ei:
        json_api.fetch_json_api(_URL, records_path="data.missing")
    assert ei.value.code == "NO_TABULAR_DATA"
    assert ei.value.status == 400


# --- Rule 2: top-level array --------------------------------------------------

def test_rule2_top_level_array(monkeypatch):
    payload = [{"x": 1, "y": 2}, {"x": 3, "y": 4}]
    _patch_get(monkeypatch, FakeResponse(200, payload))
    df, _ = json_api.fetch_json_api(_URL)
    assert df.shape == (2, 2)
    assert set(df.columns) == {"x", "y"}


# --- Rule 3: object with a single array-valued key ---------------------------

def test_rule3_single_array_key(monkeypatch):
    payload = {"meta": {"page": 1}, "rows": [{"v": 10}, {"v": 20}]}
    _patch_get(monkeypatch, FakeResponse(200, payload))
    df, _ = json_api.fetch_json_api(_URL)
    assert df.shape[0] == 2
    assert list(df.columns) == ["v"]


# --- Rule 4: json_normalize fallback on flat object --------------------------

def test_rule4_flat_object_fallback(monkeypatch):
    payload = {"name": "north", "revenue": 100}
    _patch_get(monkeypatch, FakeResponse(200, payload))
    df, _ = json_api.fetch_json_api(_URL)
    assert df.shape[0] == 1
    assert set(df.columns) == {"name", "revenue"}


# --- Error taxonomy -----------------------------------------------------------

def test_non_200_fetch_failed(monkeypatch):
    _patch_get(monkeypatch, FakeResponse(500, {}))
    with pytest.raises(SourceError) as ei:
        json_api.fetch_json_api(_URL)
    assert ei.value.code == "FETCH_FAILED"
    assert ei.value.status == 502


def test_timeout_fetch_failed(monkeypatch):
    _patch_get(monkeypatch, raise_exc=httpx.TimeoutException("timed out"))
    with pytest.raises(SourceError) as ei:
        json_api.fetch_json_api(_URL)
    assert ei.value.code == "FETCH_FAILED"
    assert ei.value.status == 502


def test_http_error_fetch_failed(monkeypatch):
    _patch_get(monkeypatch, raise_exc=httpx.HTTPError("boom"))
    with pytest.raises(SourceError) as ei:
        json_api.fetch_json_api(_URL)
    assert ei.value.code == "FETCH_FAILED"
    assert ei.value.status == 502


def test_invalid_json_body(monkeypatch):
    resp = FakeResponse(200, content=b"<<not json>>", raise_json=True)
    _patch_get(monkeypatch, resp)
    with pytest.raises(SourceError) as ei:
        json_api.fetch_json_api(_URL)
    assert ei.value.code == "JSON_PARSE_FAILED"
    assert ei.value.status == 400


def test_empty_records_no_tabular_data(monkeypatch):
    _patch_get(monkeypatch, FakeResponse(200, []))
    with pytest.raises(SourceError) as ei:
        json_api.fetch_json_api(_URL)
    assert ei.value.code == "NO_TABULAR_DATA"
    assert ei.value.status == 400


def test_file_too_large(monkeypatch):
    monkeypatch.setenv("AGENT_MAX_UPLOAD_MB", "0")
    _patch_get(monkeypatch, FakeResponse(200, [{"x": 1}]))
    with pytest.raises(SourceError) as ei:
        json_api.fetch_json_api(_URL)
    assert ei.value.code == "FILE_TOO_LARGE"
    assert ei.value.status == 413

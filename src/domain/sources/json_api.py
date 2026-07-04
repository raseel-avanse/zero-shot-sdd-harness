"""JSON-API source adapter.

GETs a user-supplied JSON endpoint, normalizes the body to a dataframe per the
four pinned rules, and converges on the same ingest path as CSV upload.
See spec/capabilities/data-sources.md and spec/api.md.
"""
from __future__ import annotations

from urllib.parse import urlparse

import httpx
import pandas as pd

from config.settings import get_settings
from domain.sources import SourceError


def _validate_url(url: str) -> str:
    if not url or not url.strip():
        raise SourceError("INVALID_URL", "A JSON-API URL is required.", 400)
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise SourceError("INVALID_URL", "URL must be a valid http(s) endpoint.", 400)
    return url.strip()


def _resolve_records(body: object, records_path: str | None) -> object:
    """Apply the four pinned normalization rules; returns the value handed to
    pandas (an array of records, or the raw body for json_normalize fallback)."""
    # Rule 1: explicit dot-path → resolve to the array.
    if records_path:
        node = body
        for key in records_path.split("."):
            if not isinstance(node, dict) or key not in node:
                raise SourceError(
                    "NO_TABULAR_DATA",
                    f"records_path '{records_path}' not found in response.",
                    400,
                )
            node = node[key]
        return node

    # Rule 2: top-level array of objects.
    if isinstance(body, list):
        return body

    # Rule 3: object with a single array-valued key.
    if isinstance(body, dict):
        array_keys = [k for k, v in body.items() if isinstance(v, list)]
        if len(array_keys) == 1:
            return body[array_keys[0]]

    # Rule 4: fall back to json_normalize on the whole body.
    return body


def _to_dataframe(records: object, body: object, used_fallback: bool) -> pd.DataFrame:
    try:
        if used_fallback:
            df = pd.json_normalize(body)
        else:
            df = pd.DataFrame(records)
    except Exception as exc:  # noqa: BLE001
        raise SourceError("NO_TABULAR_DATA", f"Could not tabularize JSON: {exc}", 400)
    return df


def fetch_json_api(url: str, records_path: str | None = None) -> tuple[pd.DataFrame, str]:
    """Fetch + normalize a JSON endpoint → (dataframe, derived title)."""
    settings = get_settings()
    clean_url = _validate_url(url)

    try:
        resp = httpx.get(
            clean_url, timeout=settings.fetch_timeout_s, follow_redirects=True
        )
    except httpx.HTTPError as exc:
        raise SourceError("FETCH_FAILED", f"Could not fetch the endpoint: {exc}", 502)

    if resp.status_code != 200:
        raise SourceError(
            "FETCH_FAILED", f"Endpoint returned HTTP {resp.status_code}.", 502
        )

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(resp.content) > max_bytes:
        raise SourceError(
            "FILE_TOO_LARGE",
            f"Fetched response exceeds the {settings.max_upload_mb} MB limit.",
            413,
        )

    try:
        body = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise SourceError("JSON_PARSE_FAILED", f"Response is not valid JSON: {exc}", 400)

    records = _resolve_records(body, records_path)
    used_fallback = records is body and not isinstance(body, list)
    df = _to_dataframe(records, body, used_fallback)

    if df.shape[1] == 0 or df.shape[0] == 0:
        raise SourceError(
            "NO_TABULAR_DATA", "No tabular records resolved from the JSON.", 400
        )

    parsed = urlparse(clean_url)
    title = f"{parsed.netloc}{parsed.path}".rstrip("/") or parsed.netloc
    return df, title

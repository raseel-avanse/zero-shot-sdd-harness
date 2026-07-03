"""Public Google Sheets source adapter (no credential).

Extracts the spreadsheet id + gid from a share URL, fetches the public
CSV-export URL over plain HTTP, and parses with the SAME pandas.read_csv path
as a CSV upload. Private/auth-gated sheets return Google's HTML login page
instead of CSV → SHEET_NOT_ACCESSIBLE. See spec/capabilities/data-sources.md.
"""
from __future__ import annotations

import io
import re

import httpx
import pandas as pd

from config.settings import get_settings
from domain.sources import SourceError

_SHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")
_GID_RE = re.compile(r"[#?&]gid=([0-9]+)")


def extract_sheet_id_and_gid(url: str) -> tuple[str, str]:
    """Parse the spreadsheet id and gid from a Google Sheets URL.

    gid defaults to "0" when absent. Raises INVALID_SHEET_URL when the url is
    blank or has no extractable spreadsheet id.
    """
    if not url or not url.strip():
        raise SourceError("INVALID_SHEET_URL", "A Google Sheet URL is required.", 400)

    id_match = _SHEET_ID_RE.search(url)
    if not id_match:
        raise SourceError(
            "INVALID_SHEET_URL",
            "Not a parseable Google Sheets URL (no spreadsheet id found).",
            400,
        )
    sheet_id = id_match.group(1)
    gid_match = _GID_RE.search(url)
    gid = gid_match.group(1) if gid_match else "0"
    return sheet_id, gid


def build_export_url(sheet_id: str, gid: str) -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/export?format=csv&gid={gid}"
    )


def _looks_like_html(content_type: str, body: bytes) -> bool:
    if "text/html" in content_type.lower():
        return True
    head = body[:512].lstrip().lower()
    return head.startswith(b"<!doctype") or head.startswith(b"<html")


def fetch_google_sheet(url: str) -> tuple[pd.DataFrame, str]:
    """Fetch a public Google Sheet as CSV → (dataframe, derived title)."""
    settings = get_settings()
    sheet_id, gid = extract_sheet_id_and_gid(url)
    export_url = build_export_url(sheet_id, gid)

    try:
        resp = httpx.get(
            export_url, timeout=settings.fetch_timeout_s, follow_redirects=True
        )
    except httpx.HTTPError as exc:
        raise SourceError("FETCH_FAILED", f"Could not fetch the sheet: {exc}", 502)

    if resp.status_code != 200:
        raise SourceError(
            "FETCH_FAILED",
            f"Sheet fetch returned HTTP {resp.status_code}.",
            502,
        )

    body = resp.content
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(body) > max_bytes:
        raise SourceError(
            "FILE_TOO_LARGE",
            f"Fetched sheet exceeds the {settings.max_upload_mb} MB limit.",
            413,
        )

    content_type = resp.headers.get("content-type", "")
    if _looks_like_html(content_type, body):
        raise SourceError(
            "SHEET_NOT_ACCESSIBLE",
            "The sheet is not publicly readable. Share it as "
            '"anyone with the link can view" and try again.',
            400,
        )

    try:
        df = pd.read_csv(io.BytesIO(body))
    except Exception as exc:  # noqa: BLE001 — surface any parse failure
        raise SourceError("PARSE_FAILED", f"Could not parse sheet CSV: {exc}", 400)

    if df.shape[1] == 0 or df.shape[0] == 0:
        raise SourceError("PARSE_FAILED", "Sheet has no data rows/columns.", 400)

    title = f"Google Sheet {sheet_id[:8]}"
    return df, title

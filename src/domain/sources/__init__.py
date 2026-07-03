"""Source adapters — load a dataframe from an external source (Google Sheets,
JSON API). Each adapter raises a typed :class:`SourceError` on failure; the API
layer maps the ``code``/``status`` onto the pinned envelope via ``api_error``.

All sources converge on the SAME ingest path as CSV upload (see
``src.api.datasets._ingest_dataframe``) so every downstream (ask / replay /
sessions) is unchanged. See spec/capabilities/data-sources.md and spec/api.md.
"""
from __future__ import annotations


class SourceError(Exception):
    """A typed source-adapter failure carrying the pinned api envelope fields."""

    def __init__(self, code: str, detail: str, status: int) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status


__all__ = ["SourceError"]

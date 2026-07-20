"""Export surface: one-click engagement dossier download (Phase 3).

`GET /engagements/{engagement_id}/export?format=md|pdf|json` returns the full
dossier — engagement metadata, the authorization/scope record, ALL findings, and
per-run token/cost totals — rendered to the requested format.

These endpoints return raw file downloads (Content-Disposition: attachment), NOT
the `{data, error}` JSON envelope used by the rest of the API. Errors (unknown
engagement, bad format) still raise the standard `api_error` HTTPException so the
error envelope stays consistent.
"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from api._common import api_error
from db.models import Engagement
from db.session import get_session
from export import build_dossier, render_json, render_markdown, render_pdf

log = logging.getLogger("sentinel.api.export")

router = APIRouter()

_FORMATS = {
    "md": ("text/markdown; charset=utf-8", "md", render_markdown),
    "json": ("application/json", "json", render_json),
    "pdf": ("application/pdf", "pdf", render_pdf),
}


def _safe_slug(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", (name or "engagement").strip()).strip("-")
    return slug or "engagement"


@router.get("/engagements/{engagement_id}/export")
def export_engagement(
    engagement_id: str,
    format: str = Query("md"),
    session: Session = Depends(get_session),
) -> Response:
    fmt = (format or "md").lower()
    if fmt not in _FORMATS:
        raise api_error(
            "INVALID_FORMAT",
            f"unsupported export format '{format}'; expected one of md, pdf, json",
            400,
        )

    engagement = session.get(Engagement, engagement_id)
    if engagement is None:
        raise api_error("NOT_FOUND", f"engagement {engagement_id} not found", 404)

    media_type, ext, renderer = _FORMATS[fmt]
    dossier = build_dossier(session, engagement)
    body = renderer(dossier)

    filename = f"dossier-{_safe_slug(engagement.name)}-{engagement.id[:8]}.{ext}"
    log.info(
        "dossier exported",
        extra={
            "engagement_id": engagement.id,
            "format": fmt,
            "bytes": len(body),
            "findings": dossier["summary"]["finding_count"],
        },
    )
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

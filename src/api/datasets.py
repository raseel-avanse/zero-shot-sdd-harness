"""Dataset upload + ask endpoints (spec/api.md)."""
from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

from api._common import ok, api_error
from config.settings import get_settings
from db.session import create_db_session
from domain.dataset_store import get_store
from domain.profile import build_profile, build_sample
from domain.sessions import (
    create_session,
    resolve_session_for_dataset,
    touch_session,
)
from domain.sources import SourceError
from domain.sources.json_api import fetch_json_api
from domain.sources.sheets import fetch_google_sheet
from graph.runner import (
    run_ask,
    DatasetNotFound,
    LLMUnavailable,
    RunFailed,
)
from observability.events import get_logger

router = APIRouter(prefix="/api")
_log = get_logger("api")


class AskRequest(BaseModel):
    question: str


class GoogleSheetRequest(BaseModel):
    url: str


class JsonApiRequest(BaseModel):
    url: str
    records_path: str | None = None


def _ingest_dataframe(df: pd.DataFrame, title: str) -> dict:
    """Shared convergence point for ALL sources (CSV / Sheets / JSON).

    Build profile + sample, store the in-memory dataframe, create a new session
    (snapshotting the profile), and return the pinned
    ``{session_id, dataset_id, profile}`` envelope — byte-for-byte identical
    regardless of source, so every downstream (ask / replay / sessions) is
    unchanged.
    """
    profile = build_profile(df)
    sample = build_sample(df)
    dataset_id = get_store().add(df, profile, sample)

    with create_db_session() as session:
        session_id = create_session(
            session, dataset_id=dataset_id, title=title, profile=profile
        )

    _log.info(
        "ingest_dataframe",
        dataset_id=dataset_id,
        session_id=session_id,
        rows=profile["row_count"],
        title=title,
    )
    return ok({"session_id": session_id, "dataset_id": dataset_id, "profile": profile})


@router.post("/datasets")
async def upload_dataset(file: UploadFile = File(...)) -> dict:
    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        raise api_error("UNSUPPORTED_TYPE", "Only CSV uploads are supported in Phase 1.", 400)

    raw = await file.read()
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    if len(raw) > max_bytes:
        raise api_error(
            "FILE_TOO_LARGE",
            f"File exceeds the {get_settings().max_upload_mb} MB limit.",
            413,
        )

    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise api_error("PARSE_FAILED", f"Could not parse CSV: {exc}", 400)

    if df.shape[1] == 0 or df.shape[0] == 0:
        raise api_error("PARSE_FAILED", "CSV has no data rows/columns.", 400)

    # Phase 2+3: converge on the shared ingest path (session + profile + store).
    return _ingest_dataframe(df, filename)


@router.post("/datasets/from-google-sheet")
def load_google_sheet(req: GoogleSheetRequest) -> dict:
    """Phase 3: load a public Google Sheet URL → same shape as CSV upload."""
    try:
        df, title = fetch_google_sheet(req.url)
    except SourceError as exc:
        raise api_error(exc.code, exc.detail, exc.status)
    return _ingest_dataframe(df, title)


@router.post("/datasets/from-json-api")
def load_json_api(req: JsonApiRequest) -> dict:
    """Phase 3: load a JSON-API endpoint → same shape as CSV upload."""
    try:
        df, title = fetch_json_api(req.url, req.records_path)
    except SourceError as exc:
        raise api_error(exc.code, exc.detail, exc.status)
    return _ingest_dataframe(df, title)


@router.post("/datasets/{dataset_id}/ask")
def ask_dataset(dataset_id: str, req: AskRequest) -> dict:
    question = (req.question or "").strip()
    if not question:
        raise api_error("EMPTY_QUESTION", "Question must not be blank.", 422)

    if dataset_id not in get_store():
        raise api_error("DATASET_NOT_FOUND", "Dataset not found (may have expired).", 404)

    # Phase 2: resolve the session that owns this dataset_id (server-side).
    with create_db_session() as session:
        sess = resolve_session_for_dataset(session, dataset_id)
        session_id = sess.id if sess is not None else None

    try:
        card = run_ask(dataset_id, question, session_id=session_id)
    except DatasetNotFound:
        raise api_error("DATASET_NOT_FOUND", "Dataset not found (may have expired).", 404)
    except LLMUnavailable as exc:
        raise api_error("LLM_UNAVAILABLE", f"LLM unavailable: {exc}", 502)
    except RunFailed as exc:
        raise api_error("RUN_FAILED", f"Run failed: {exc}", 500)

    # Bump session activity after a successful turn.
    if session_id is not None:
        with create_db_session() as session:
            touch_session(session, session_id)

    return ok(card)

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

    profile = build_profile(df)
    sample = build_sample(df)
    dataset_id = get_store().add(df, profile, sample)

    # Phase 2: each upload starts a new session and snapshots the profile so
    # history can render after the in-memory dataframe is evicted.
    with create_db_session() as session:
        session_id = create_session(
            session, dataset_id=dataset_id, title=filename, profile=profile
        )

    _log.info(
        "upload_dataset",
        dataset_id=dataset_id,
        session_id=session_id,
        rows=profile["row_count"],
    )
    return ok({"session_id": session_id, "dataset_id": dataset_id, "profile": profile})


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

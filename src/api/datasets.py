"""Dataset upload + ask endpoints (spec/api.md)."""
from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

from api._common import ok, api_error
from config.settings import get_settings
from domain.dataset_store import get_store
from domain.profile import build_profile, build_sample
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
    _log.info("upload_dataset", dataset_id=dataset_id, rows=profile["row_count"])
    return ok({"dataset_id": dataset_id, "profile": profile})


@router.post("/datasets/{dataset_id}/ask")
def ask_dataset(dataset_id: str, req: AskRequest) -> dict:
    question = (req.question or "").strip()
    if not question:
        raise api_error("EMPTY_QUESTION", "Question must not be blank.", 422)

    if dataset_id not in get_store():
        raise api_error("DATASET_NOT_FOUND", "Dataset not found (may have expired).", 404)

    try:
        card = run_ask(dataset_id, question)
    except DatasetNotFound:
        raise api_error("DATASET_NOT_FOUND", "Dataset not found (may have expired).", 404)
    except LLMUnavailable as exc:
        raise api_error("LLM_UNAVAILABLE", f"LLM unavailable: {exc}", 502)
    except RunFailed as exc:
        raise api_error("RUN_FAILED", f"Run failed: {exc}", 500)

    return ok(card)

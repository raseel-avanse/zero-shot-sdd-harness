from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from urllib.parse import urlparse

from api._common import ok, api_error
from db.session import get_session
from db.models import RunRow, DealRow
from domain.run import RunRequest, AnswerRequest, RunResponse
from graph.runner import start_run, resume_run

router = APIRouter()

_VALID_QUERY_TYPES = {"name", "url", "category"}


def _looks_like_url(text: str) -> bool:
    parsed = urlparse(text)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


@router.post("/runs")
def create_run(req: RunRequest) -> dict:
    query_type = (req.query_type or "name").strip().lower()
    query_text = (req.query_text or "").strip()
    if not query_text:
        raise api_error("VALIDATION", "query_text is required and must be non-empty", 400)
    if query_type not in _VALID_QUERY_TYPES:
        raise api_error(
            "VALIDATION",
            f"query_type must be one of {sorted(_VALID_QUERY_TYPES)}",
            400,
        )
    if query_type == "url" and not _looks_like_url(query_text):
        raise api_error(
            "VALIDATION",
            "query_text must be a valid http(s) product URL for query_type=url",
            400,
        )
    # category is free text — no extra shape validation beyond non-empty.
    run_id = start_run(query_type, query_text)
    return ok({"run_id": run_id, "status": "running"})


@router.post("/runs/{run_id}/answer")
def answer_run(
    run_id: str, req: AnswerRequest, session: Session = Depends(get_session)
) -> dict:
    answer = (req.answer or "").strip()
    if not answer:
        raise api_error("VALIDATION", "answer is required and must be non-empty", 400)

    run = session.get(RunRow, run_id)
    if run is None:
        raise api_error("NOT_FOUND", f"Run {run_id} not found", 404)
    if run.status != "needs_input":
        raise api_error(
            "CONFLICT",
            f"Run {run_id} is not awaiting an answer (status={run.status})",
            409,
        )

    resume_run(run_id, answer)
    return ok({"run_id": run_id, "status": "running"})


@router.get("/runs/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    run = session.get(RunRow, run_id)
    if run is None:
        raise api_error("NOT_FOUND", f"Run {run_id} not found", 404)

    deals = (
        session.query(DealRow)
        .filter(DealRow.run_id == run_id)
        .order_by(DealRow.rank)
        .all()
    )
    deal_dicts = [
        {
            "rank": d.rank,
            "site": d.site,
            "price_inr": d.price_inr,
            "reason": d.reason,
            "quality_label": d.quality_label,
            "quality_reason": d.quality_reason,
            "source_url": d.source_url,
        }
        for d in deals
    ]

    return ok(
        RunResponse(
            run_id=run.id,
            status=run.status,
            progress_step=run.progress_step,
            clarifying_question=run.clarifying_question,
            deals=deal_dicts,
            prompt_tokens=run.prompt_tokens or 0,
            completion_tokens=run.completion_tokens or 0,
            cost_inr=run.cost_inr,
            error=run.error_message,
        ).model_dump()
    )

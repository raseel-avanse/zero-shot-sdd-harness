from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.session import get_session
from db.models import RunRow, DealRow
from domain.run import RunRequest, RunResponse
from graph.runner import start_run

router = APIRouter()


@router.post("/runs")
def create_run(req: RunRequest) -> dict:
    query_text = (req.query_text or "").strip()
    if not query_text:
        raise api_error("VALIDATION", "query_text is required and must be non-empty", 400)
    run_id = start_run(req.query_type or "name", query_text)
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

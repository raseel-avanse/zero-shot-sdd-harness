import json
from pathlib import Path

from config.settings import get_settings
from db.models import RunRow, DealRow
from db.session import create_db_session
from domain.deal import Deal
from graph.state import AgentState
from llm.client import LLMClient
from observability.events import get_logger
from tools.pricing import estimate_cost

_PROMPTS = Path(__file__).parent.parent / "prompts"
_NOTES_CHAR_LIMIT = 8000

log = get_logger("graph.nodes")


def _load_prompt(name: str) -> str:
    return (_PROMPTS / name).read_text(encoding="utf-8").strip()


def friendly_error(exc: Exception, *, stage: str = "research") -> str:
    """Map a raw provider/parse exception to a plain-language, user-safe message.

    The raw exception detail is NEVER included — callers must log the full
    exception separately for debugging. This keeps provider JSON, model names,
    and stack traces out of the user-facing `error` field.
    """
    text = f"{type(exc).__name__} {exc}".lower()

    rate_limit_markers = ("429", "resource_exhausted", "rate limit", "ratelimit", "quota", "too many requests")
    reach_markers = ("timeout", "timed out", "connection", "connect", "unavailable",
                     "500", "502", "503", "504", "deadline")

    if any(m in text for m in rate_limit_markers):
        return "The research service is busy right now — please try again in a minute."
    if any(m in text for m in reach_markers):
        return "Couldn't reach the research service — please try again."
    if stage == "rank":
        return "Couldn't rank the results — please try again."
    return "Something went wrong during research — please try again."


def _update_run(run_id: str, **fields) -> None:
    """Persist progress/status fields to the run row from within a worker thread."""
    with create_db_session() as session:
        run = session.get(RunRow, run_id)
        if run is None:
            return
        for key, value in fields.items():
            setattr(run, key, value)


# ---------------------------------------------------------------------------
# research
# ---------------------------------------------------------------------------
def research(state: AgentState) -> AgentState:
    run_id = state["run_id"]
    query_text = state.get("query_text", "")
    query_type = state.get("query_type", "name")
    try:
        _update_run(run_id, progress_step="searching")
        log.info("node.research.start", run_id=run_id, query_type=query_type)

        client = LLMClient(provider="gemini")
        prompt = f"Product ({query_type}): {query_text}\n\nResearch this and return trimmed notes."
        result = client.generate(prompt, system=_load_prompt("research.md"), grounding=True)

        notes = (result.text or "").strip()[:_NOTES_CHAR_LIMIT]
        _update_run(
            run_id,
            progress_step="reviewing",
            prompt_tokens=state.get("prompt_tokens", 0) + result.prompt_tokens,
            completion_tokens=state.get("completion_tokens", 0) + result.completion_tokens,
        )
        log.info(
            "llm.call",
            node="research",
            run_id=run_id,
            model=client.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            grounding_sources=len(result.sources),
        )
        return {
            **state,
            "research_notes": notes,
            "grounding_sources": result.sources,
            "prompt_tokens": state.get("prompt_tokens", 0) + result.prompt_tokens,
            "completion_tokens": state.get("completion_tokens", 0) + result.completion_tokens,
            "progress_step": "reviewing",
        }
    except Exception as exc:  # noqa: BLE001 — node boundary
        log.error("node.research.error", run_id=run_id, error=str(exc))
        return {**state, "error": friendly_error(exc, stage="research")}


# ---------------------------------------------------------------------------
# rank
# ---------------------------------------------------------------------------
def _parse_deals(raw: str) -> list[Deal]:
    """Parse the model's JSON output into validated Deal objects. Raises on failure."""
    text = raw.strip()
    if text.startswith("```"):
        # strip markdown code fences if the model added them despite instructions
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    text = text.strip()
    data = json.loads(text)
    items = data.get("deals", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("Expected a JSON list of deals")
    deals = [Deal(**item) for item in items]
    return deals[:5]


def rank(state: AgentState) -> AgentState:
    run_id = state["run_id"]
    try:
        _update_run(run_id, progress_step="ranking")
        log.info("node.rank.start", run_id=run_id)

        client = LLMClient(provider="gemini")
        system = _load_prompt("rank.md")
        base = (
            f"Product: {state.get('query_text', '')}\n\n"
            f"Research notes:\n{state.get('research_notes', '')}"
        )

        prompt_tokens = state.get("prompt_tokens", 0)
        completion_tokens = state.get("completion_tokens", 0)

        deals: list[Deal] = []
        last_err: Exception | None = None
        for attempt in range(2):  # initial + one retry on parse failure
            reminder = "" if attempt == 0 else "\n\nReturn VALID JSON ONLY, no prose, no fences."
            result = client.generate(base + reminder, system=system, grounding=False)
            prompt_tokens += result.prompt_tokens
            completion_tokens += result.completion_tokens
            log.info(
                "llm.call",
                node="rank",
                run_id=run_id,
                model=client.model,
                attempt=attempt,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
            )
            try:
                deals = _parse_deals(result.text)
                last_err = None
                break
            except Exception as exc:  # noqa: BLE001 — parse retry
                last_err = exc
                log.info("node.rank.parse_retry", run_id=run_id, error=str(exc))

        if last_err is not None:
            raise last_err

        # Attach grounding source URLs (best-effort) so deals can cite a listing.
        sources = state.get("grounding_sources") or []
        deal_dicts = []
        for i, deal in enumerate(deals):
            d = deal.model_dump()
            if d.get("source_url") is None and i < len(sources):
                d["source_url"] = sources[i]
            deal_dicts.append(d)

        return {
            **state,
            "deals": deal_dicts,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "progress_step": "ranking",
        }
    except Exception as exc:  # noqa: BLE001 — node boundary
        log.error("node.rank.error", run_id=run_id, error=str(exc))
        return {**state, "error": friendly_error(exc, stage="rank")}


# ---------------------------------------------------------------------------
# finalize
# ---------------------------------------------------------------------------
def finalize(state: AgentState) -> AgentState:
    run_id = state["run_id"]
    prompt_tokens = state.get("prompt_tokens", 0)
    completion_tokens = state.get("completion_tokens", 0)
    deals = state.get("deals", []) or []
    model = get_settings().llm_model or "gemini-2.5-flash"
    cost = estimate_cost(prompt_tokens, completion_tokens, model)

    with create_db_session() as session:
        run = session.get(RunRow, run_id)
        if run is not None:
            run.status = "completed"
            run.progress_step = "done"
            run.prompt_tokens = prompt_tokens
            run.completion_tokens = completion_tokens
            run.cost_inr = cost
            run.research_notes = state.get("research_notes")
        for d in deals:
            session.add(
                DealRow(
                    run_id=run_id,
                    rank=d["rank"],
                    site=d["site"],
                    price_inr=d["price_inr"],
                    reason=d["reason"],
                    quality_label=d.get("quality_label"),
                    quality_reason=d.get("quality_reason"),
                    source_url=d.get("source_url"),
                )
            )

    log.info(
        "run.completed",
        run_id=run_id,
        deals=len(deals),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_inr=cost,
    )
    return {**state, "cost_inr": cost, "progress_step": "done", "status": "completed"}


# ---------------------------------------------------------------------------
# handle_error
# ---------------------------------------------------------------------------
def handle_error(state: AgentState) -> AgentState:
    run_id = state.get("run_id")
    message = state.get("error") or "Research failed"
    log.error("run.failed", run_id=run_id, error=message)
    if run_id:
        _update_run(run_id, status="failed", error_message=message)
    return {**state, "status": "failed"}

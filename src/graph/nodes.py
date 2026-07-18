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
from tools.deal_quality import parse_quality_response, merge_quality

_PROMPTS = Path(__file__).parent.parent / "prompts"
_NOTES_CHAR_LIMIT = 8000

log = get_logger("graph.nodes")

# Per query-type instruction blocks appended to the shared research prompt so
# the research node behaves correctly for name / url / category modes.
_MODE_INSTRUCTIONS = {
    "name": (
        "MODE: PRODUCT NAME. The input is a product name. Research this specific "
        "product and cross-check its price across Indian sites."
    ),
    "url": (
        "MODE: PRODUCT URL. The input is a product-page URL from an Indian "
        "marketplace. First identify the exact product the URL points to (brand, "
        "model, variant), then find and cross-check listings for that SAME product "
        "(or the closest comparable item) across the other Indian sites. Anchor the "
        "ranking to that identified product — do not drift to unrelated items."
    ),
    "category": (
        "MODE: CATEGORY. The input is a product category, optionally with a budget "
        "or constraint (e.g. 'gaming laptops under 80k'). Interpret the category and "
        "any stated constraint, DISCOVER a handful of strong candidate products in "
        "that category yourself, then find the best current listing for each. Honour "
        "any stated budget. The best-value picks may be DIFFERENT products, not five "
        "listings of one item."
    ),
}


def _load_prompt(name: str) -> str:
    return (_PROMPTS / name).read_text(encoding="utf-8").strip()


def _build_research_prompt(query_type: str, query_text: str, clarify_answer: str | None) -> str:
    mode = _MODE_INSTRUCTIONS.get(query_type, _MODE_INSTRUCTIONS["name"])
    parts = [mode, "", f"Query ({query_type}): {query_text}"]
    if clarify_answer:
        parts.append(f"\nThe shopper clarified: {clarify_answer}")
    parts.append("\nResearch this and return trimmed notes.")
    return "\n".join(parts)


def _parse_clarify_json(raw: str) -> tuple[bool, str]:
    """Parse the clarify judge's JSON into (needs_clarification, question)."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    text = text.strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object for the clarify decision")
    needs = bool(data.get("needs_clarification", False))
    question = str(data.get("question", "") or "").strip()
    if needs and not question:
        needs = False  # no usable question -> do not gate
    return needs, question


def check_clarification(query_type: str, query_text: str) -> tuple[bool, str]:
    """Ask Gemini (one cheap, non-grounded call) whether the query is too
    ambiguous to rank, and if so compose ONE question.

    URL queries anchor a specific product and are never gated (saves a call).
    On any provider/parse failure, degrade to NOT gating (proceed to research).
    """
    if query_type == "url":
        return False, ""
    try:
        client = LLMClient(provider="gemini")
        result = client.generate(
            f"Query ({query_type}): {query_text}",
            system=_load_prompt("clarify.md"),
            grounding=False,
        )
        return _parse_clarify_json(result.text)
    except Exception as exc:  # noqa: BLE001 — degrade to not-gating on any failure
        log.info("node.clarify.check_failed", error=str(exc))
        return False, ""


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
    clarify_answer = state.get("clarify_answer")
    try:
        # Clarify gate (P2): only on the first pass (no answer yet). If the query
        # is too vague to rank, pause the run BEFORE researching — set the
        # question, persist status=needs_input, and return early. Clear queries
        # (and resumes, which carry a clarify_answer) skip the gate entirely.
        if not clarify_answer:
            needs, question = check_clarification(query_type, query_text)
            log.info(
                "node.clarify.decision",
                run_id=run_id,
                query_type=query_type,
                needs_clarification=needs,
                question=question or None,
            )
            if needs:
                _update_run(
                    run_id,
                    status="needs_input",
                    progress_step="queued",
                    clarifying_question=question,
                )
                return {
                    **state,
                    "needs_clarification": True,
                    "clarifying_question": question,
                }

        _update_run(run_id, progress_step="searching")
        log.info("node.research.start", run_id=run_id, query_type=query_type,
                 resumed=bool(clarify_answer))

        client = LLMClient(provider="gemini")
        prompt = _build_research_prompt(query_type, query_text, clarify_answer)
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
# deal_quality (P2)
# ---------------------------------------------------------------------------
def deal_quality(state: AgentState) -> AgentState:
    """Judge, in ONE batched grounded Gemini call, whether each ranked deal is a
    genuine discount / a good time to buy. Degrades every deal to `unknown`
    rather than failing the run when grounding or parsing is thin.
    """
    run_id = state["run_id"]
    deals = state.get("deals", []) or []
    prompt_tokens = state.get("prompt_tokens", 0)
    completion_tokens = state.get("completion_tokens", 0)

    _update_run(run_id, progress_step="assessing")
    log.info("node.deal_quality.start", run_id=run_id, deals=len(deals))

    if not deals:
        return {**state, "progress_step": "assessing"}

    try:
        client = LLMClient(provider="gemini")
        listing = "\n".join(
            f"- rank {d.get('rank')}: {d.get('site')} — ₹{d.get('price_inr')} "
            f"({d.get('reason', '')})"
            for d in deals
        )
        prompt = (
            f"Product context: {state.get('query_text', '')}\n\n"
            f"Ranked deals to assess:\n{listing}"
        )
        result = client.generate(
            prompt, system=_load_prompt("deal_quality.md"), grounding=True
        )
        prompt_tokens += result.prompt_tokens
        completion_tokens += result.completion_tokens
        log.info(
            "llm.call",
            node="deal_quality",
            run_id=run_id,
            model=client.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            grounding_sources=len(result.sources),
        )
        assessments = parse_quality_response(result.text)
    except Exception as exc:  # noqa: BLE001 — degrade, never fatal
        log.info("node.deal_quality.degraded", run_id=run_id, error=str(exc))
        assessments = {}

    labelled = merge_quality(deals, assessments)
    labelled_count = sum(1 for d in labelled if d.get("quality_label") != "unknown")
    log.info(
        "node.deal_quality.done",
        run_id=run_id,
        labelled=labelled_count,
        total=len(labelled),
    )
    return {
        **state,
        "deals": labelled,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "progress_step": "assessing",
    }


# ---------------------------------------------------------------------------
# finalize
# ---------------------------------------------------------------------------
def finalize(state: AgentState) -> AgentState:
    run_id = state["run_id"]
    prompt_tokens = state.get("prompt_tokens", 0)
    completion_tokens = state.get("completion_tokens", 0)
    deals = state.get("deals", []) or []
    model = get_settings().llm_model or "gemini-flash-latest"
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

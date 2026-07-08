"""Chat surface: interactive chat with turn memory over a loaded engagement.

`POST /engagements/{id}/chat` accepts a user message, loads the prior turns for
the engagement (conversation memory), passes the accumulated transcript plus
engagement/findings context to Gemini so the reply DEPENDS on prior turns, then
persists BOTH the user turn and the assistant reply to `chat_turns` and returns
the assistant message. `GET /engagements/{id}/chat` lists the turns for the UI.

Scope is per-engagement; each follow-up sees the earlier turns (spec/data.md
ChatTurn + spec/capabilities/live-probing-chat-retest.md business rules).
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api._common import api_error, ok
from db.models import ChatTurn, Engagement, Finding
from db.session import get_session
from domain.chat import ChatMessageRequest, ChatTurnOut

logger = logging.getLogger("sentinel.chat")

router = APIRouter()

_SYSTEM = (
    "You are Sentinel, a whitebox information-security assistant helping a "
    "security engineer direct follow-up probes over a single loaded engagement. "
    "You are given the engagement context, its validated findings, and the prior "
    "conversation turns. Use the conversation history to answer follow-up "
    "questions that depend on earlier turns. Be concise, technical, and specific. "
    "Never invent findings that are not in the provided context."
)


def _prior_turns(session: Session, engagement_id: str) -> list[ChatTurn]:
    return list(
        session.execute(
            select(ChatTurn)
            .where(ChatTurn.engagement_id == engagement_id)
            .order_by(ChatTurn.created_at.asc(), ChatTurn.id.asc())
        ).scalars().all()
    )


def _engagement_context(engagement: Engagement, findings: list[Finding]) -> str:
    lines = [
        "=== ENGAGEMENT ===",
        f"name: {engagement.name}",
        f"target_type: {engagement.target_type}",
        f"target_ref: {engagement.target_ref}",
        f"status: {engagement.status}",
        "",
        "=== FINDINGS ===",
    ]
    if not findings:
        lines.append("(no findings recorded yet)")
    for f in findings:
        lines.append(
            f"- [{f.severity_label}/{f.confidence}/{f.status}] {f.category}: "
            f"{f.title} @ {f.location} — {f.description}"
        )
    return "\n".join(lines)


def _build_prompt(context: str, turns: list[ChatTurn], message: str) -> str:
    parts = [context, "", "=== CONVERSATION SO FAR ==="]
    if not turns:
        parts.append("(no prior turns)")
    for t in turns:
        speaker = "User" if t.role == "user" else "Sentinel"
        parts.append(f"{speaker}: {t.content}")
    parts.append(f"User: {message}")
    parts.append("Sentinel:")
    return "\n".join(parts)


@router.post("/engagements/{engagement_id}/chat")
def chat(
    engagement_id: str,
    req: ChatMessageRequest,
    session: Session = Depends(get_session),
) -> dict:
    engagement = session.get(Engagement, engagement_id)
    if engagement is None:
        raise api_error("NOT_FOUND", f"engagement {engagement_id} not found", 404)

    started = time.monotonic()
    findings = list(
        session.execute(
            select(Finding)
            .where(Finding.engagement_id == engagement_id)
            .order_by(Finding.created_at.asc())
        ).scalars().all()
    )
    turns = _prior_turns(session, engagement_id)

    context = _engagement_context(engagement, findings)
    prompt = _build_prompt(context, turns, req.message)

    try:
        from llm.client import LLMClient

        result = LLMClient().complete(prompt, system=_SYSTEM, tier="fast")
        reply = (result.get("text") or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.exception("chat LLM call failed for engagement %s", engagement_id)
        raise api_error("LLM_ERROR", f"chat generation failed: {exc}", 502)

    if not reply:
        raise api_error("LLM_EMPTY", "chat model returned an empty reply", 502)

    try:
        user_turn = ChatTurn(
            engagement_id=engagement_id, role="user", content=req.message
        )
        assistant_turn = ChatTurn(
            engagement_id=engagement_id, role="assistant", content=reply
        )
        session.add(user_turn)
        session.add(assistant_turn)
        session.flush()
        turn_id = assistant_turn.id
    except Exception as exc:  # noqa: BLE001
        raise api_error("DB_WRITE_FAILED", f"could not persist chat turns: {exc}", 500)

    latency_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        "chat engagement=%s prior_turns=%d msg_len=%d reply_len=%d latency_ms=%d",
        engagement_id,
        len(turns),
        len(req.message),
        len(reply),
        latency_ms,
    )
    return ok({"reply": reply, "turn_id": turn_id})


@router.get("/engagements/{engagement_id}/chat")
def list_chat(engagement_id: str, session: Session = Depends(get_session)) -> dict:
    engagement = session.get(Engagement, engagement_id)
    if engagement is None:
        raise api_error("NOT_FOUND", f"engagement {engagement_id} not found", 404)
    turns = _prior_turns(session, engagement_id)
    items = [
        ChatTurnOut(
            id=t.id,
            engagement_id=t.engagement_id,
            role=t.role,
            content=t.content,
            created_at=t.created_at,
        ).model_dump()
        for t in turns
    ]
    return ok(items)

"""Pydantic request/response models for the chat surface (spec/api.md — [P2]).

Interactive chat with turn memory scoped to an engagement:
`POST /engagements/{id}/chat` accepts a message and returns the assistant reply;
`GET /engagements/{id}/chat` lists prior turns for the UI.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatReplyResponse(BaseModel):
    reply: str
    turn_id: str


class ChatTurnOut(BaseModel):
    id: str
    engagement_id: str
    role: str
    content: str
    created_at: datetime

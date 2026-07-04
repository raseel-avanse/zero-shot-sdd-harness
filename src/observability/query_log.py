"""Append-only JSON-lines query log (spec/capabilities/transparency-log.md).

Complementary to the runs DB row. Never fails the request — failures are
logged via structlog and swallowed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from config.settings import get_settings
from observability.events import get_logger

_log = get_logger("query_log")


def append_query_log(
    *,
    dataset_id: str,
    question: str,
    answer: str | None,
    token_total: int,
    attempts: int,
    ok: bool,
) -> None:
    line = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "question": question,
        "answer": answer,
        "token_total": token_total,
        "attempts": attempts,
        "ok": ok,
    }
    try:
        path = Path(get_settings().query_log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line) + "\n")
    except Exception as exc:  # never fail the request over logging
        _log.warning("query_log_append_failed", error=str(exc))

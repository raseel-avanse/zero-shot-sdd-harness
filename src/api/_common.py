from typing import Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from fastapi.requests import Request


def ok(data: Any) -> dict:
    return {"ok": True, "data": data}


class APIError(HTTPException):
    """HTTPException whose detail carries the spec error envelope fields."""

    def __init__(self, code: str, detail: str, status_code: int = 400) -> None:
        super().__init__(status_code=status_code, detail={"code": code, "detail": detail})
        self.code = code
        self.error_detail = detail


def api_error(code: str, detail: str, status_code: int = 400) -> APIError:
    return APIError(code, detail, status_code)


async def api_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Render HTTPExceptions in the spec envelope: {"ok": false, "error": {...}}."""
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        error = {"code": detail.get("code"), "detail": detail.get("detail")}
    else:
        error = {"code": _status_code_name(exc.status_code), "detail": str(detail)}
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": error})


def _status_code_name(status_code: int) -> str:
    return {
        400: "BAD_REQUEST",
        404: "NOT_FOUND",
        413: "FILE_TOO_LARGE",
        422: "UNPROCESSABLE_ENTITY",
        500: "INTERNAL_ERROR",
        502: "LLM_UNAVAILABLE",
    }.get(status_code, "ERROR")

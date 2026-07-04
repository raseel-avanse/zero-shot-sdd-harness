"""Local pandas executor — runs LLM-generated code in-process against a df.

Trust boundary: this executes un-sandboxed generated Python. Acceptable ONLY
for the single trusted local user (see spec/architecture.md § trust boundary).
Bounded by a wall-clock timeout. Never raises — captures the traceback string.

The timeout is enforced with a worker thread + join(timeout) so it works in any
thread (the graph runs off the main thread under FastAPI/TestClient), unlike
signal.alarm which is main-thread-only.
"""
from __future__ import annotations

import io
import contextlib
import threading
import traceback
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class ExecResult:
    ok: bool
    result_repr: str | None
    stdout: str
    traceback: str | None


def _run(code: str, namespace: dict, stdout: io.StringIO, box: dict) -> None:
    try:
        with contextlib.redirect_stdout(stdout):
            exec(compile(code, "<generated_code>", "exec"), namespace)
        box["done"] = True
    except BaseException:  # noqa: BLE001 — capture everything, never raise
        box["traceback"] = traceback.format_exc()


def execute_pandas(code: str, df: pd.DataFrame, timeout_s: int = 15) -> ExecResult:
    """Run `code` against `df`. The code must assign its answer to `result`.

    Returns ExecResult; never raises. Operates on a defensive copy of df.
    """
    namespace: dict = {"df": df.copy(), "pd": pd, "np": np}
    stdout = io.StringIO()
    box: dict = {}

    worker = threading.Thread(
        target=_run, args=(code, namespace, stdout, box), daemon=True
    )
    worker.start()
    worker.join(timeout_s if timeout_s and timeout_s > 0 else None)

    if worker.is_alive():
        # Cannot force-kill a thread; report a timeout. The daemon thread will
        # be reaped on process exit.
        return ExecResult(
            ok=False,
            result_repr=None,
            stdout=stdout.getvalue(),
            traceback=f"TimeoutError: execution exceeded {timeout_s}s timeout",
        )

    if "traceback" in box:
        return ExecResult(
            ok=False,
            result_repr=None,
            stdout=stdout.getvalue(),
            traceback=box["traceback"],
        )

    if "result" not in namespace:
        return ExecResult(
            ok=False,
            result_repr=None,
            stdout=stdout.getvalue(),
            traceback="NameError: generated code did not assign a variable named 'result'",
        )

    return ExecResult(
        ok=True,
        result_repr=_repr_result(namespace["result"]),
        stdout=stdout.getvalue(),
        traceback=None,
    )


def _repr_result(result) -> str:
    if isinstance(result, (pd.DataFrame, pd.Series)):
        return result.to_string()
    if isinstance(result, np.generic):  # numpy scalar → plain Python value
        return repr(result.item())
    return repr(result)

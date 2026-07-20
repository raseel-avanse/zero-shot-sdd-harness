"""Bounded, best-effort sandboxed PoC execution.

Phase 1 sandbox guarantees:
  * runs in a constrained subprocess with a hard wall-clock timeout;
  * working dir is an ISOLATED TEMP COPY of the target repo — the real target
    is never mutated and no PoC artifacts land inside the assessed repo;
  * a stripped environment with no network-credential leakage and PROXY vars
    forced to a dead address to discourage outbound network use;
  * output truncated so nothing large is captured.

This is a *bounded local check*, not a full container jail. A PoC that runs
clean here raises finding confidence; a failure/timeout leaves the finding
`unconfirmed` (static evidence retained) and the run continues.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

_DEFAULT_TIMEOUT = 10          # seconds, wall clock
_MAX_OUTPUT = 8_000            # chars per stream


def sandbox_run(script: str, workdir: str | None = None, timeout: int = _DEFAULT_TIMEOUT) -> dict:
    """Execute a Python PoC snippet in a constrained subprocess.

    ``workdir`` is treated as the SOURCE target repo to reason against. It is
    never used as the live cwd — the PoC runs inside an isolated temp COPY of
    that repo (created in a ``TemporaryDirectory`` and discarded afterward), so
    the real target is never mutated and no artifacts leak into the assessed
    repo. When no source is given, a fresh empty temp dir is used.

    Returns {ran, exit_code, stdout, stderr, timed_out, error}. Never raises.
    """
    result = {
        "ran": False, "exit_code": None, "stdout": "", "stderr": "",
        "timed_out": False, "error": None,
    }

    with tempfile.TemporaryDirectory(prefix="sentinel_poc_") as tmp:
        cwd = tmp
        # Copy the target into an isolated sandbox root so the PoC can read the
        # code under test without any chance of mutating the real repo.
        if workdir and os.path.isdir(workdir):
            cwd = os.path.join(tmp, "target")
            try:
                shutil.copytree(
                    workdir, cwd,
                    symlinks=True,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "node_modules"),
                )
            except Exception:  # noqa: BLE001 — fall back to an empty sandbox on copy failure
                cwd = tmp

        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": cwd,
            "TMPDIR": cwd,
            "http_proxy": "http://127.0.0.1:9",
            "https_proxy": "http://127.0.0.1:9",
            "no_proxy": "",
            "PYTHONDONTWRITEBYTECODE": "1",
        }

        script_path = os.path.join(cwd, "_poc_check.py")
        try:
            with open(script_path, "w", encoding="utf-8") as fh:
                fh.write(script)
            proc = subprocess.run(
                [sys.executable, "-I", script_path],
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            result.update(
                ran=True,
                exit_code=proc.returncode,
                stdout=(proc.stdout or "")[:_MAX_OUTPUT],
                stderr=(proc.stderr or "")[:_MAX_OUTPUT],
            )
        except subprocess.TimeoutExpired:
            result.update(timed_out=True, error="timeout")
        except Exception as exc:  # noqa: BLE001 — sandbox failure must never crash the run
            result.update(error=str(exc))
    return result

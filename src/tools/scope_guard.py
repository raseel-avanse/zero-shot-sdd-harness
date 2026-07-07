"""In-code scope allowlist enforcement (SAFETY-CRITICAL).

A target is allowed ONLY when its resolved absolute path is contained inside
one of the resolved authorized-target paths. This is a pure containment check
— never delegated to the LLM prompt.
"""
from __future__ import annotations

import os


def _norm(path: str) -> str:
    # Resolve symlinks/.. and normalise; do NOT require existence so the guard
    # can refuse before ever touching the filesystem.
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def is_contained(target: str, allowed: str) -> bool:
    t = _norm(target)
    a = _norm(allowed)
    if t == a:
        return True
    # Contained iff t starts with a + separator (avoids /foo matching /foobar).
    return t.startswith(a + os.sep)


def check(target: str, allowlist: list[str]) -> bool:
    """Return True iff `target` falls inside at least one allowlist entry."""
    if not target or not allowlist:
        return False
    return any(is_contained(target, entry) for entry in allowlist if entry)

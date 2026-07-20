"""In-code scope allowlist enforcement (SAFETY-CRITICAL).

A target is allowed ONLY when its resolved absolute path is contained inside
one of the resolved authorized-target paths. This is a pure containment check
— never delegated to the LLM prompt.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit


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
    """Return True iff `target` falls inside at least one allowlist entry.

    Repo/path containment check — the Phase-1 behaviour, unchanged.
    """
    if not target or not allowlist:
        return False
    return any(is_contained(target, entry) for entry in allowlist if entry)


# --------------------------------------------------------------------------- #
# Live-app host scope (Phase 2) — SAFETY-CRITICAL.
#
# A live target URL is in scope ONLY when its host matches the host of an
# allowlisted authorized target. Allowlist entries may be bare hosts
# ("example.com", "example.com:8443") or full URLs ("https://example.com/api").
# Matching is on hostname (case-insensitive); port and path are ignored so an
# authorized host authorizes any endpoint on that host but NEVER another host.
# --------------------------------------------------------------------------- #


def extract_host(value: str) -> str:
    """Return the lowercased hostname of a URL or bare host string, or ""."""
    if not value:
        return ""
    v = value.strip()
    # urlsplit only populates netloc when a scheme (or leading //) is present.
    parts = urlsplit(v if "//" in v else "//" + v)
    host = parts.hostname or ""
    return host.lower()


def host_matches(target: str, allowed: str) -> bool:
    """True iff `target` resolves to the same host as `allowed` (both non-empty)."""
    th = extract_host(target)
    ah = extract_host(allowed)
    return bool(th) and bool(ah) and th == ah


def check_live(target: str, allowlist: list[str]) -> bool:
    """Return True iff live `target`'s host matches at least one allowlist entry."""
    if not target or not allowlist:
        return False
    return any(host_matches(target, entry) for entry in allowlist if entry)


def check_target(target: str, allowlist: list[str], target_type: str) -> bool:
    """Dispatch to the correct in-code scope check for the target type.

    `live_app` -> host allowlist; anything else (repo) -> path containment.
    """
    if target_type == "live_app":
        return check_live(target, allowlist)
    return check(target, allowlist)

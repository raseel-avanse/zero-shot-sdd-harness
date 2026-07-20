"""Optional OpenAPI/Swagger endpoint ingestion (Phase 4, OWASP API profile).

Given a spec source — a URL (treated as a probe: verb + host + budget guarded
via the existing `http_probe.Prober`, GET only, non-destructive) or a local
file path (read directly) — parse it and return the list of documented
endpoints as `{"method", "path", "params"}` dicts.

SAFETY / PRIVACY:
  * URL sources go through the SAME in-code guards as any live probe: only
    GET/HEAD/OPTIONS verbs, host must be in the scope allowlist, per-session
    request budget. An out-of-scope host is refused BEFORE any request.
  * The raw spec content is NEVER returned or persisted — only the derived,
    bounded endpoint list. The caller (live_recon) discards everything else.
  * On any failure (no source, unreachable, unparseable) this returns an empty
    list so the caller falls back to light base-URL discovery — never fatal.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from tools import http_probe

log = logging.getLogger("sentinel.tools.openapi_ingest")

# HTTP methods we surface from an OpenAPI path item. Enumeration is read-only
# (we only LIST documented operations); the live prober re-guards every actual
# request and will never issue a mutating verb regardless of what is documented.
_HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")

# Bound the number of endpoints we extract to keep run state small.
_MAX_ENDPOINTS = 200


def _looks_like_url(ref: str) -> bool:
    r = ref.strip().lower()
    return r.startswith("http://") or r.startswith("https://")


def _load_text_from_url(ref: str, allowlist: list[str]) -> str:
    """Fetch a spec URL through the guarded, read-only prober (GET only)."""
    with http_probe.Prober(allowlist) as prober:
        # `probe` enforces verb + host + budget guards before any request.
        meta = prober.probe(ref, method="GET")
    return meta.get("body_excerpt", "") or ""


def _load_text_from_file(ref: str) -> str:
    return Path(ref).read_text(encoding="utf-8")


def _parse_spec(text: str) -> dict[str, Any]:
    """Parse a spec document (JSON, or YAML if PyYAML is available)."""
    text = text.strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    try:  # YAML is optional — only used if the dependency is present.
        import yaml  # type: ignore

        parsed = yaml.safe_load(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:  # noqa: BLE001 — any YAML failure => treat as unparseable
        pass
    return {}


def _extract_params(operation: Any, shared: Any) -> list[str]:
    """Collect parameter names from a path item + operation (best-effort)."""
    names: list[str] = []
    for source in (shared, operation):
        if isinstance(source, dict):
            for p in source.get("parameters", []) or []:
                if isinstance(p, dict) and p.get("name"):
                    names.append(str(p["name"]))
    # Preserve order, drop duplicates.
    seen: set[str] = set()
    return [n for n in names if not (n in seen or seen.add(n))]


def extract_endpoints(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Return `{method, path, params}` for every documented operation."""
    endpoints: list[dict[str, Any]] = []
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        return endpoints
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        shared = item  # path-level `parameters` are shared across operations
        for method in _HTTP_METHODS:
            operation = item.get(method)
            if operation is None:
                continue
            endpoints.append(
                {
                    "method": method.upper(),
                    "path": str(path),
                    "params": _extract_params(operation, shared),
                }
            )
            if len(endpoints) >= _MAX_ENDPOINTS:
                return endpoints
    return endpoints


def load(ref: str | None, allowlist: list[str] | None) -> list[dict[str, Any]]:
    """Fetch/read + parse an OpenAPI/Swagger source; return the endpoint list.

    Returns an empty list on any failure (no source, out-of-scope/unreachable
    URL, unreadable file, unparseable spec) so the caller falls back to light
    discovery. The raw spec content is never returned or persisted.
    """
    if not ref or not ref.strip():
        return []
    ref = ref.strip()
    allow = list(allowlist or [])
    try:
        if _looks_like_url(ref):
            text = _load_text_from_url(ref, allow)
        else:
            text = _load_text_from_file(ref)
    except http_probe.ProbeError as exc:
        # Out-of-scope / unsafe / budget — refused in code. Fall back safely.
        log.warning("openapi_ingest: url refused by guard", extra={"ref": ref, "err": str(exc)})
        return []
    except (httpx.HTTPError, OSError) as exc:
        log.warning("openapi_ingest: source unreadable", extra={"ref": ref, "err": str(exc)})
        return []

    spec = _parse_spec(text)
    if not spec:
        log.warning("openapi_ingest: spec unparseable", extra={"ref": ref})
        return []
    return extract_endpoints(spec)

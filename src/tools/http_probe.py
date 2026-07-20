"""Non-destructive, read-only HTTP probe helper (SAFETY-CRITICAL, Phase 2).

Every probe is guarded IN CODE, independent of the LLM, BEFORE any request
leaves the process:

  1. Verb guard   — only GET/HEAD/OPTIONS (settings.probe_allowed_methods). Any
                    mutating verb (POST/PUT/PATCH/DELETE/…) is refused.
  2. Host guard   — the URL's host must match the engagement's scope allowlist
                    (tools.scope_guard.check_live). An out-of-scope host is
                    refused WITHOUT issuing a request.
  3. Budget guard — a hard cap on the number of requests per session
                    (settings.probe_max_requests) bounds blast radius / cost /
                    anti-DoS. Requests also carry a timeout.

Responses are returned as bounded metadata only — status, a capped set of
headers (sensitive values redacted), and a bounded body excerpt. Raw dumps and
secrets are never returned in full, so nothing large or sensitive is persisted.
Redirects are NOT followed (a redirect must never carry a probe off-host).
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from config.settings import get_settings
from tools import scope_guard

log = logging.getLogger("sentinel.tools.http_probe")

# Absolute in-code ceiling of safe verbs. settings.probe_allowed_methods may
# only ever be a SUBSET of this — a mutating verb can never be enabled.
_SAFE_VERBS = frozenset({"GET", "HEAD", "OPTIONS"})

# Header names whose values may carry session secrets — redact in returned meta.
_SENSITIVE_HEADERS = frozenset({"set-cookie", "authorization", "www-authenticate", "proxy-authenticate"})

# Only surface a bounded, useful set of response headers.
_MAX_HEADERS = 32


class ProbeError(Exception):
    """Base class for in-code probe refusals / failures."""


class UnsafeMethodError(ProbeError):
    """A non-read-only / mutating HTTP verb was requested — refused in code."""


class OutOfScopeError(ProbeError):
    """The target host is not in the engagement scope allowlist — refused in code."""


class ProbeBudgetExceeded(ProbeError):
    """The per-session request cap was hit — refused in code (anti-DoS)."""


def _resolve_allowed_methods(explicit: list[str] | None) -> frozenset[str]:
    raw = explicit if explicit is not None else get_settings().probe_allowed_methods
    methods = {m.strip().upper() for m in (raw or []) if m and m.strip()}
    # Intersect with the absolute safe set: a mutating verb can NEVER slip in
    # via config. If misconfigured to empty, fall back to the safe defaults.
    safe = methods & _SAFE_VERBS
    return frozenset(safe) if safe else frozenset(_SAFE_VERBS)


class Prober:
    """A bounded, scope-guarded, read-only HTTP prober for one probe session.

    Holds the scope allowlist + guards and a running request counter. Reuse a
    single instance per assessment run so the request cap is enforced across
    all probes in that run.
    """

    def __init__(
        self,
        allowlist: list[str],
        *,
        allowed_methods: list[str] | None = None,
        max_requests: int | None = None,
        timeout_seconds: float | None = None,
        max_body_bytes: int | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        s = get_settings()
        self.allowlist = list(allowlist or [])
        self.allowed_methods = _resolve_allowed_methods(allowed_methods)
        self.max_requests = int(max_requests if max_requests is not None else s.probe_max_requests)
        self.timeout_seconds = float(
            timeout_seconds if timeout_seconds is not None else s.probe_timeout_seconds
        )
        self.max_body_bytes = int(
            max_body_bytes if max_body_bytes is not None else s.probe_max_body_bytes
        )
        self._client = client
        self._owns_client = client is None
        self._count = 0

    # -- guards (all raise BEFORE any request is issued) -------------------- #

    def _guard(self, url: str, method: str) -> str:
        m = (method or "").strip().upper()
        # Verb guard first — cheapest, and a mutating verb is always a hard no.
        if m not in self.allowed_methods:
            log.warning("probe refused: unsafe verb", extra={"method": m, "url": url})
            raise UnsafeMethodError(
                f"unsafe HTTP verb '{m}': only {sorted(self.allowed_methods)} are permitted"
            )
        # Host guard — refuse out-of-scope hosts with NO request sent.
        if not scope_guard.check_live(url, self.allowlist):
            log.warning("probe refused: out-of-scope host", extra={"url": url})
            raise OutOfScopeError(f"host for '{url}' is not within the authorized scope allowlist")
        # Budget guard — anti-DoS cap on request count.
        if self._count >= self.max_requests:
            raise ProbeBudgetExceeded(
                f"probe request budget exhausted ({self.max_requests} requests)"
            )
        return m

    # -- probing ------------------------------------------------------------ #

    @property
    def request_count(self) -> int:
        return self._count

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout_seconds, follow_redirects=False
            )
        return self._client

    def probe(self, url: str, method: str = "GET") -> dict[str, Any]:
        """Issue ONE guarded, read-only request; return bounded response metadata.

        Raises UnsafeMethodError / OutOfScopeError / ProbeBudgetExceeded (all
        before any network call) on a guard violation.
        """
        m = self._guard(url, method)
        self._count += 1  # count the attempt so a flood cannot bypass the cap

        started = time.monotonic()
        client = self._get_client()
        # follow_redirects=False is set on the client; pass explicitly too in
        # case a caller injected a client without it.
        resp = client.request(m, url, follow_redirects=False)
        elapsed_ms = int((time.monotonic() - started) * 1000)

        return {
            "url": url,
            "method": m,
            "status": resp.status_code,
            "headers": self._safe_headers(resp.headers),
            "body_excerpt": self._body_excerpt(resp),
            "elapsed_ms": elapsed_ms,
        }

    # -- bounding / redaction ---------------------------------------------- #

    def _safe_headers(self, headers: httpx.Headers) -> dict[str, str]:
        out: dict[str, str] = {}
        for i, (k, v) in enumerate(headers.items()):
            if i >= _MAX_HEADERS:
                break
            if k.lower() in _SENSITIVE_HEADERS:
                out[k] = "[REDACTED]"
            else:
                out[k] = v[:256]
        return out

    def _body_excerpt(self, resp: httpx.Response) -> str:
        if resp.request is not None and resp.request.method == "HEAD":
            return ""
        try:
            raw = resp.content[: self.max_body_bytes]
        except Exception:  # noqa: BLE001 — never let body handling crash a probe
            return ""
        text = raw.decode(resp.encoding or "utf-8", errors="replace")
        return text[: self.max_body_bytes]

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "Prober":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

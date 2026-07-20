"""Intentionally-vulnerable fixture REST API (stdlib-only) for OWASP API tests.

A tiny, self-contained HTTP API built on ``http.server`` — NO third-party deps —
that deliberately exhibits several OWASP API Security Top 10 (2023) weaknesses so
Sentinel's OWASP-API assessment profile has a real, reproducible target to hunt.

It is READ-ONLY-friendly: every vulnerability is observable via GET so a
non-destructive (GET/HEAD/OPTIONS only) probe can find it. No endpoint mutates
state. Never deploy this — it is a test fixture only.

Endpoints and the OWASP API category each demonstrates
------------------------------------------------------
  GET /                       Index / endpoint listing (harmless).
  GET /openapi.json           Minimal OpenAPI-ish doc for endpoint enumeration.

  GET /api/users/{id}         API1:2023 — Broken Object Level Authorization (BOLA).
                              Returns ANY user's record (incl. email/SSN/salary)
                              by predictable integer id, with NO authorization
                              check. Fetching id=2 while you "are" user 1 leaks
                              another user's PII.
  GET /api/orders/{id}        API1:2023 — BOLA. Any order returned by sequential
                              id with no ownership check.

  GET /api/admin              API2:2023 — Broken Authentication. A "protected"
                              admin endpoint that returns sensitive data with NO
                              credentials required at all.
  GET /api/account            API2:2023 — Broken Authentication. Accepts ANY
                              value in the Authorization header (even absent /
                              "Bearer x") and returns account secrets — the token
                              is never actually validated.

  GET /api/debug              API8:2023 — Security Misconfiguration. A debug
                              endpoint that echoes server config, environment,
                              and secrets. Also, no security headers are set on
                              any response.
  GET /api/boom               API8:2023 — Security Misconfiguration. Triggers a
                              verbose, stack-trace-like 500 error body that leaks
                              internal implementation details.

Usage
-----
    server = make_server(0)            # 0 = pick a free port
    port = server.server_address[1]
    import threading; threading.Thread(target=server.serve_forever).start()
    ...
    server.shutdown()

or run standalone:

    python tests/fixtures/vuln_api_app.py 8099
"""
from __future__ import annotations

import json
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# --- Seeded, deliberately-leaky data ---------------------------------------- #

# Note the PII (email, ssn, salary) — a BOLA leak exposes all of it.
_USERS = {
    1: {"id": 1, "username": "alice", "email": "alice@example.com",
        "ssn": "111-11-1111", "salary": 90000, "role": "user"},
    2: {"id": 2, "username": "bob", "email": "bob@example.com",
        "ssn": "222-22-2222", "salary": 120000, "role": "user"},
    3: {"id": 3, "username": "carol", "email": "carol@example.com",
        "ssn": "333-33-3333", "salary": 250000, "role": "admin"},
}

_ORDERS = {
    1001: {"id": 1001, "user_id": 1, "total": 42.50, "card_last4": "4242"},
    1002: {"id": 1002, "user_id": 2, "total": 999.00, "card_last4": "1881"},
    1003: {"id": 1003, "user_id": 3, "total": 12.00, "card_last4": "0007"},
}

# Deliberately-exposed "config" (API8). Real secrets would live in env — leaking
# them from a debug endpoint is the misconfiguration.
_DEBUG_CONFIG = {
    "env": "production",
    "debug": True,
    "db_url": "postgresql://admin:s3cr3t@db.internal:5432/app",
    "jwt_secret": "hunter2-do-not-share",
    "aws_access_key_id": "AKIAFAKEFAKEFAKE1234",
    "feature_flags": {"new_billing": True},
}

_OPENAPI = {
    "openapi": "3.0.0",
    "info": {"title": "Vulnerable Fixture API", "version": "0.0.1"},
    "paths": {
        "/api/users/{id}": {"get": {"summary": "Get a user by id"}},
        "/api/orders/{id}": {"get": {"summary": "Get an order by id"}},
        "/api/admin": {"get": {"summary": "Admin dashboard data"}},
        "/api/account": {"get": {"summary": "Current account details"}},
        "/api/debug": {"get": {"summary": "Debug / config dump"}},
    },
}


class _Handler(BaseHTTPRequestHandler):
    # Quiet: suppress the default per-request stderr logging noise.
    def log_message(self, *args, **kwargs):  # noqa: D102, ANN002, ANN003
        return

    server_version = "VulnFixture/0.0.1"

    # --- response helpers --------------------------------------------------- #

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # API8: NO security headers are set (no X-Content-Type-Options,
        # X-Frame-Options, Strict-Transport-Security, etc.).
        self.end_headers()
        self.wfile.write(body)

    # --- routing ------------------------------------------------------------ #

    def do_HEAD(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Allow", "GET, HEAD, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802, C901
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        try:
            if path == "/":
                self._send_json(200, {
                    "service": "vulnerable-fixture-api",
                    "endpoints": [
                        "/api/users/{id}", "/api/orders/{id}", "/api/admin",
                        "/api/account", "/api/debug", "/openapi.json",
                    ],
                })
                return

            if path == "/openapi.json":
                self._send_json(200, _OPENAPI)
                return

            # API1:2023 — BOLA: any user by predictable id, no authz check.
            if path.startswith("/api/users/"):
                uid = int(path.rsplit("/", 1)[1])
                user = _USERS.get(uid)
                if user is None:
                    self._send_json(404, {"error": "no such user"})
                else:
                    self._send_json(200, user)  # full PII, no ownership check
                return

            # API1:2023 — BOLA: any order by sequential id, no ownership check.
            if path.startswith("/api/orders/"):
                oid = int(path.rsplit("/", 1)[1])
                order = _ORDERS.get(oid)
                if order is None:
                    self._send_json(404, {"error": "no such order"})
                else:
                    self._send_json(200, order)
                return

            # API2:2023 — Broken Authentication: admin data with NO credentials.
            if path == "/api/admin":
                self._send_json(200, {
                    "dashboard": "admin",
                    "total_users": len(_USERS),
                    "all_ssns": [u["ssn"] for u in _USERS.values()],
                    "note": "no authentication required to view this",
                })
                return

            # API2:2023 — Broken Authentication: accepts ANY / no token.
            if path == "/api/account":
                token = self.headers.get("Authorization", "")
                # The token is never validated — any value (or none) works.
                self._send_json(200, {
                    "authenticated_as": "carol (admin)",
                    "token_seen": token or "<none>",
                    "token_validated": False,
                    "api_keys": ["sk-live-FAKEFAKEFAKE"],
                })
                return

            # API8:2023 — Security Misconfiguration: debug/config dump.
            if path == "/api/debug":
                self._send_json(200, _DEBUG_CONFIG)
                return

            # API8:2023 — Security Misconfiguration: verbose stack-trace error.
            if path == "/api/boom":
                raise RuntimeError("simulated internal failure in billing module")

            self._send_json(404, {"error": "not found", "path": path})

        except Exception as exc:  # noqa: BLE001
            # API8: leak a full stack trace + internals in the error body.
            self._send_json(500, {
                "error": str(exc),
                "type": type(exc).__name__,
                "traceback": traceback.format_exc(),
                "config_hint": _DEBUG_CONFIG["db_url"],
            })


def make_server(port: int = 0, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    """Build (but do not start) the vulnerable fixture server on ``port``.

    Pass ``port=0`` to have the OS assign a free port; read it back from
    ``server.server_address[1]``.
    """
    return ThreadingHTTPServer((host, port), _Handler)


def run(port: int = 8099, host: str = "127.0.0.1") -> None:
    """Start the server and serve forever (blocking)."""
    server = make_server(port, host)
    actual = server.server_address[1]
    print(f"vulnerable fixture API listening on http://{host}:{actual}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    _port = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
    run(_port)

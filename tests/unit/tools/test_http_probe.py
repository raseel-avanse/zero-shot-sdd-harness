"""Unit tests for the SAFETY-CRITICAL non-destructive HTTP probe (Phase 2).

No live network: an httpx.MockTransport backs the client. These assert the
in-code guards refuse unsafe verbs, out-of-scope hosts (WITHOUT issuing a
request), and enforce the request budget — independent of any LLM.
"""
import httpx
import pytest

from tools import http_probe


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def _ok_handler():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        return httpx.Response(
            200,
            headers={"Server": "nginx", "Set-Cookie": "session=supersecret"},
            text="hello world " * 500,
        )

    return handler, calls


# -- happy path --------------------------------------------------------------- #

def test_safe_get_probe_returns_bounded_metadata():
    handler, calls = _ok_handler()
    prober = http_probe.Prober(
        ["https://target.example.com"],
        client=_client(handler),
        max_body_bytes=64,
    )
    result = prober.probe("https://target.example.com/api", method="GET")

    assert result["status"] == 200
    assert result["method"] == "GET"
    assert calls == [("GET", "https://target.example.com/api")]
    # Body is bounded, sensitive header redacted.
    assert len(result["body_excerpt"]) <= 64
    # httpx normalises header names to lowercase; sensitive value is redacted.
    redacted = {k.lower(): v for k, v in result["headers"].items()}
    assert redacted["set-cookie"] == "[REDACTED]"
    assert prober.request_count == 1


# -- error path: mutating verb refused in code -------------------------------- #

@pytest.mark.parametrize("verb", ["POST", "PUT", "PATCH", "DELETE", "TRACE", "post"])
def test_mutating_verb_refused_without_request(verb):
    handler, calls = _ok_handler()
    prober = http_probe.Prober(["https://target.example.com"], client=_client(handler))

    with pytest.raises(http_probe.UnsafeMethodError):
        prober.probe("https://target.example.com/", method=verb)

    # No request was ever issued; counter untouched.
    assert calls == []
    assert prober.request_count == 0


def test_mutating_verb_cannot_be_enabled_via_config():
    # Even if misconfigured to include POST, the absolute safe set wins.
    handler, calls = _ok_handler()
    prober = http_probe.Prober(
        ["https://target.example.com"],
        allowed_methods=["GET", "POST", "DELETE"],
        client=_client(handler),
    )
    assert "POST" not in prober.allowed_methods
    assert "DELETE" not in prober.allowed_methods
    with pytest.raises(http_probe.UnsafeMethodError):
        prober.probe("https://target.example.com/", method="POST")
    assert calls == []


# -- error path: out-of-scope host refused BEFORE any request ----------------- #

def test_out_of_scope_host_refused_without_request():
    handler, calls = _ok_handler()
    prober = http_probe.Prober(["https://target.example.com"], client=_client(handler))

    with pytest.raises(http_probe.OutOfScopeError):
        prober.probe("https://evil.example.net/", method="GET")

    assert calls == []
    assert prober.request_count == 0


def test_in_scope_matches_host_ignoring_port_and_path():
    handler, calls = _ok_handler()
    prober = http_probe.Prober(["target.example.com"], client=_client(handler))
    prober.probe("https://target.example.com:8443/deep/path?x=1", method="HEAD")
    assert calls == [("HEAD", "https://target.example.com:8443/deep/path?x=1")]


# -- edge case: request budget cap (anti-DoS) --------------------------------- #

def test_request_budget_enforced():
    handler, calls = _ok_handler()
    prober = http_probe.Prober(
        ["https://target.example.com"], max_requests=2, client=_client(handler)
    )
    prober.probe("https://target.example.com/a")
    prober.probe("https://target.example.com/b")
    with pytest.raises(http_probe.ProbeBudgetExceeded):
        prober.probe("https://target.example.com/c")

    # Only the two permitted requests hit the transport.
    assert len(calls) == 2
    assert prober.request_count == 2

"""Unit tests for the Phase-4 OWASP API Security Top 10 (2023) profile.

Pure/no-network where possible:
  * the category-key -> canonical `APIn:2023 — …` mapping (all ten),
  * `openapi_ingest` endpoint extraction (inline spec + file) with NO raw spec
    content returned/persisted, and URL sources refused when out of scope,
  * profile branching selects the OWASP taxonomy + `owasp_api_*` prompts inside
    prioritize / live_hunt (LLM stubbed to capture the system prompt; no key).
"""
from __future__ import annotations

import json

import pytest

import graph.nodes as nodes
from graph.nodes import (
    _OWASP_API_KEYS,
    _OWASP_API_TAXONOMY,
    _categories_for_profile,
    _hunt_prompt,
    _prioritize_prompt,
    owasp_api_ref,
)
from tools import http_probe, openapi_ingest


# --------------------------------------------------------------------------- #
# Taxonomy mapping — canonical APIn:2023 refs for all ten categories.
# --------------------------------------------------------------------------- #

_EXPECTED = {
    "api1_bola": "API1:2023 — Broken Object Level Authorization",
    "api2_broken_auth": "API2:2023 — Broken Authentication",
    "api3_bopla": "API3:2023 — Broken Object Property Level Authorization",
    "api4_resource_consumption": "API4:2023 — Unrestricted Resource Consumption",
    "api5_bfla": "API5:2023 — Broken Function Level Authorization",
    "api6_sensitive_flows": "API6:2023 — Unrestricted Access to Sensitive Business Flows",
    "api7_ssrf": "API7:2023 — Server Side Request Forgery",
    "api8_misconfig": "API8:2023 — Security Misconfiguration",
    "api9_inventory": "API9:2023 — Improper Inventory Management",
    "api10_unsafe_consumption": "API10:2023 — Unsafe Consumption of APIs",
}


def test_owasp_api_ref_maps_all_ten_categories():
    assert set(_OWASP_API_KEYS) == set(_EXPECTED)
    assert len(_OWASP_API_KEYS) == 10
    for key, ref in _EXPECTED.items():
        assert owasp_api_ref(key) == ref
        assert _OWASP_API_TAXONOMY[key] == ref
        # Canonical format: "APIn:2023 — Title".
        assert ref.startswith("API")
        assert ":2023 — " in ref


def test_owasp_api_ref_none_for_generic_category():
    assert owasp_api_ref("injection") is None
    assert owasp_api_ref("nonsense") is None


# --------------------------------------------------------------------------- #
# Profile branching helpers — taxonomy + prompt selection.
# --------------------------------------------------------------------------- #


def test_categories_for_profile_selects_taxonomy():
    assert _categories_for_profile("owasp_api") == _OWASP_API_KEYS
    assert _categories_for_profile("general") == nodes._CATEGORIES
    assert _categories_for_profile(None) == nodes._CATEGORIES


def test_prompt_selection_by_profile():
    assert _prioritize_prompt("owasp_api") == "owasp_api_prioritize.md"
    assert _prioritize_prompt("general") == "prioritize.md"
    assert _hunt_prompt("owasp_api") == "owasp_api_hunt.md"
    assert _hunt_prompt("general") == "hunt.md"


def test_owasp_prompt_files_exist_and_are_nonempty():
    for name in ("owasp_api_prioritize.md", "owasp_api_hunt.md"):
        assert (nodes._PROMPT_DIR / name).read_text(encoding="utf-8").strip()


# --------------------------------------------------------------------------- #
# openapi_ingest — endpoint extraction; NO raw spec content retained.
# --------------------------------------------------------------------------- #

_SAMPLE_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Vuln API", "version": "1.0.0", "x-secret": "do-not-leak"},
    "paths": {
        "/users/{id}": {
            "parameters": [{"name": "id", "in": "path"}],
            "get": {"summary": "get user"},
            "delete": {"summary": "delete user"},
        },
        "/orders": {
            "get": {"parameters": [{"name": "page", "in": "query"}]},
            "post": {"summary": "create order"},
        },
    },
}


def test_extract_endpoints_from_inline_spec():
    eps = openapi_ingest.extract_endpoints(_SAMPLE_SPEC)
    pairs = {(e["method"], e["path"]) for e in eps}
    assert ("GET", "/users/{id}") in pairs
    assert ("DELETE", "/users/{id}") in pairs
    assert ("GET", "/orders") in pairs
    assert ("POST", "/orders") in pairs
    # Params merge path-level + operation-level.
    get_user = next(e for e in eps if e["method"] == "GET" and e["path"] == "/users/{id}")
    assert "id" in get_user["params"]
    get_orders = next(e for e in eps if e["method"] == "GET" and e["path"] == "/orders")
    assert "page" in get_orders["params"]


def test_extract_endpoints_returns_only_derived_no_raw_spec():
    eps = openapi_ingest.extract_endpoints(_SAMPLE_SPEC)
    # Only the derived endpoint list is returned; no raw spec / secret leaks.
    blob = json.dumps(eps)
    assert "do-not-leak" not in blob
    assert "openapi" not in blob
    assert "info" not in blob
    for e in eps:
        assert set(e.keys()) == {"method", "path", "params"}


def test_load_from_local_file_json(tmp_path):
    spec_file = tmp_path / "openapi.json"
    spec_file.write_text(json.dumps(_SAMPLE_SPEC), encoding="utf-8")
    eps = openapi_ingest.load(str(spec_file), allowlist=[])
    assert {(e["method"], e["path"]) for e in eps} >= {("GET", "/users/{id}"), ("GET", "/orders")}


def test_load_returns_empty_on_no_source_or_bad_file(tmp_path):
    assert openapi_ingest.load(None, []) == []
    assert openapi_ingest.load("", []) == []
    assert openapi_ingest.load(str(tmp_path / "missing.json"), []) == []
    bad = tmp_path / "bad.json"
    bad.write_text("not json at all {{{", encoding="utf-8")
    assert openapi_ingest.load(str(bad), []) == []


def test_load_url_out_of_scope_refused_returns_empty():
    # An off-allowlist URL is refused by the http_probe host guard BEFORE any
    # request; load() swallows the refusal and falls back to [].
    eps = openapi_ingest.load(
        "https://evil.example.net/openapi.json", allowlist=["target.example.com"]
    )
    assert eps == []


def test_load_url_goes_through_guarded_prober(monkeypatch):
    """A URL source is fetched via a GET-only, host-guarded probe (never raw)."""
    calls: dict = {}

    class _FakeProber:
        def __init__(self, allowlist, *a, **k):
            calls["allowlist"] = allowlist

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def probe(self, url, method="GET"):
            calls["url"] = url
            calls["method"] = method
            return {"body_excerpt": json.dumps(_SAMPLE_SPEC)}

    monkeypatch.setattr(openapi_ingest.http_probe, "Prober", _FakeProber)
    eps = openapi_ingest.load(
        "https://target.example.com/openapi.json", allowlist=["target.example.com"]
    )
    assert calls["method"] == "GET"
    assert calls["allowlist"] == ["target.example.com"]
    assert {(e["method"], e["path"]) for e in eps} >= {("GET", "/orders")}


# --------------------------------------------------------------------------- #
# Profile branching inside nodes — prioritize selects the OWASP taxonomy +
# prompt (LLM stubbed; no key, no network).
# --------------------------------------------------------------------------- #


class _CapturingLLM:
    """Stub LLMClient capturing the `system` prompt and returning fixed JSON."""

    captured: list[str] = []

    def __init__(self, *a, **k):
        pass

    def complete(self, prompt, system="", tier="fast"):
        _CapturingLLM.captured.append(system)
        return {"text": json.dumps({"priorities": ["api8_misconfig", "api1_bola"]}),
                "prompt_tokens": 1, "completion_tokens": 1, "model": "stub"}


def test_prioritize_uses_owasp_taxonomy_and_prompt(monkeypatch):
    _CapturingLLM.captured = []
    monkeypatch.setattr(nodes, "LLMClient", _CapturingLLM)
    # Avoid DB writes in this pure branching test.
    monkeypatch.setattr(nodes, "_persist_progress", lambda *a, **k: None)

    owasp_prompt = nodes._load_prompt("owasp_api_prioritize.md")
    out = nodes.prioritize(
        {"assessment_profile": "owasp_api", "recon": {"summary": "an API"}, "step_count": 1}
    )
    priorities = out["priorities"]
    # Ranked keys lead, remaining OWASP keys appended; ALL ten present, no generic.
    assert priorities[:2] == ["api8_misconfig", "api1_bola"]
    assert set(priorities) == set(_OWASP_API_KEYS)
    assert "injection" not in priorities
    # The OWASP-specific prioritize prompt was used.
    assert _CapturingLLM.captured[-1] == owasp_prompt


def test_prioritize_general_profile_unchanged(monkeypatch):
    _CapturingLLM.captured = []

    class _GeneralLLM(_CapturingLLM):
        def complete(self, prompt, system="", tier="fast"):
            _CapturingLLM.captured.append(system)
            return {"text": json.dumps({"priorities": ["broken_auth"]}),
                    "prompt_tokens": 1, "completion_tokens": 1, "model": "stub"}

    monkeypatch.setattr(nodes, "LLMClient", _GeneralLLM)
    monkeypatch.setattr(nodes, "_persist_progress", lambda *a, **k: None)

    general_prompt = nodes._load_prompt("prioritize.md")
    out = nodes.prioritize({"assessment_profile": "general", "recon": {}, "step_count": 1})
    assert set(out["priorities"]) == set(nodes._CATEGORIES)
    assert _CapturingLLM.captured[-1] == general_prompt


def test_live_hunt_tags_owasp_ref_on_candidates(monkeypatch):
    """live_hunt under the OWASP profile tags each candidate with the ref."""

    class _HuntLLM:
        def __init__(self, *a, **k):
            pass

        def complete(self, prompt, system="", tier="fast"):
            _HuntLLM.system = system
            return {"text": json.dumps({"candidates": [{"title": "BOLA", "location": "/users/1"}]}),
                    "prompt_tokens": 1, "completion_tokens": 1, "model": "stub"}

    class _NoProbeProber:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def probe(self, url, method="GET"):
            return {"url": url, "method": method, "status": 200, "headers": {}, "body_excerpt": ""}

    monkeypatch.setattr(nodes, "LLMClient", _HuntLLM)
    monkeypatch.setattr(nodes.http_probe, "Prober", _NoProbeProber)
    monkeypatch.setattr(nodes, "_persist_progress", lambda *a, **k: None)

    out = nodes.live_hunt(
        {
            "assessment_profile": "owasp_api",
            "priorities": ["api1_bola", "api2_broken_auth"],
            "recon": {"endpoints": ["https://target.example.com/users/1"]},
            "target_path": "https://target.example.com",
            "scope_allowlist": ["target.example.com"],
            "step_count": 2,
            "step_budget": 40,
        }
    )
    cands = out["candidate_findings"]
    assert cands and cands[0]["category"] == "api1_bola"
    assert cands[0]["owasp_api_ref"] == "API1:2023 — Broken Object Level Authorization"
    # The OWASP hunt prompt was used.
    assert "OWASP API" in _HuntLLM.system

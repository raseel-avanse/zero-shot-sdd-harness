"""Engagement dossier export (Phase 3).

Builds a structured, self-contained dossier for one engagement — metadata,
the authorization/scope record, ALL findings, and per-run token/cost totals —
and renders it to Markdown, JSON, or a pure-python (reportlab) PDF.

Raw source is never included; only the bounded excerpts already stored on
findings (`evidence` / `suggested_patch`) are carried through.
"""
from export.dossier import build_dossier
from export.render import render_json, render_markdown, render_pdf

__all__ = ["build_dossier", "render_json", "render_markdown", "render_pdf"]

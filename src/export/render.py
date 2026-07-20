"""Render a dossier dict to Markdown, JSON, or PDF.

PDF uses reportlab (pure-python, no system/native deps). The PDF carries the
same sections as the Markdown so the three formats stay consistent.
"""
from __future__ import annotations

import io
import json

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


def render_json(dossier: dict) -> bytes:
    return json.dumps(dossier, indent=2, ensure_ascii=False).encode("utf-8")


def _fmt_cost(cost: dict) -> str:
    return (
        f"prompt={cost.get('prompt_tokens', 0)}, "
        f"completion={cost.get('completion_tokens', 0)}, "
        f"total={cost.get('total_tokens', 0)} tokens, "
        f"est. ${cost.get('estimated_cost_usd', 0):.6f}"
    )


def render_markdown(dossier: dict) -> bytes:
    eng = dossier["engagement"]
    scope = dossier.get("scope")
    findings = dossier.get("findings", [])
    cost = dossier.get("cost_totals", {})
    summary = dossier.get("summary", {})

    lines: list[str] = []
    lines.append(f"# Engagement Dossier — {eng['name']}")
    lines.append("")
    lines.append(f"_Generated: {dossier.get('generated_at', '')}_")
    lines.append("")

    lines.append("## Engagement")
    lines.append("")
    lines.append(f"- **ID:** {eng['id']}")
    lines.append(f"- **Name:** {eng['name']}")
    lines.append(f"- **Target type:** {eng['target_type']}")
    lines.append(f"- **Target:** {eng['target_ref']}")
    lines.append(f"- **Status:** {eng['status']}")
    lines.append(f"- **Created:** {eng.get('created_at', '')}")
    lines.append("")

    lines.append("## Authorization / Scope")
    lines.append("")
    if scope is None:
        lines.append("_No scope/authorization record on file._")
    else:
        lines.append(f"- **Authorized by:** {scope['authorized_by']}")
        lines.append(
            f"- **Non-destructive only:** {scope['non_destructive_only']}"
        )
        lines.append("- **Authorized targets:**")
        for t in scope.get("authorized_targets", []):
            lines.append(f"  - {t}")
        lines.append("- **Rules of engagement:**")
        lines.append("")
        lines.append(f"  {scope['rules_of_engagement']}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total findings:** {summary.get('finding_count', 0)}")
    for sev, n in (summary.get("severity_counts") or {}).items():
        lines.append(f"  - {sev}: {n}")
    lines.append(f"- **Cost totals:** {_fmt_cost(cost)}")
    lines.append("")

    lines.append("## Findings")
    lines.append("")
    if not findings:
        lines.append("_No findings recorded for this engagement._")
    for i, f in enumerate(findings, start=1):
        cvss = f.get("cvss_score")
        cvss_str = f"{cvss}" if cvss is not None else "n/a"
        lines.append(
            f"### {i}. [{(f['severity_label'] or '').upper()}] {f['title']}"
        )
        lines.append("")
        lines.append(f"- **Severity:** {f['severity_label']}")
        lines.append(f"- **CVSS:** {cvss_str}")
        lines.append(f"- **Confidence:** {f['confidence']}")
        lines.append(f"- **Category:** {f['category']}")
        lines.append(f"- **Status:** {f['status']}")
        lines.append(f"- **Location:** {f['location']}")
        lines.append("")
        lines.append(f"**Description:** {f['description']}")
        lines.append("")
        lines.append("**Evidence / PoC:**")
        lines.append("")
        lines.append("```")
        lines.append(f.get("evidence", "") or "")
        lines.append("```")
        lines.append("")
        lines.append(f"**Remediation:** {f['remediation']}")
        if f.get("suggested_patch"):
            lines.append("")
            lines.append("**Suggested patch:**")
            lines.append("")
            lines.append("```")
            lines.append(f["suggested_patch"])
            lines.append("```")
        lines.append("")

    lines.append("## Runs")
    lines.append("")
    if not dossier.get("runs"):
        lines.append("_No assessment runs recorded._")
    for r in dossier.get("runs", []):
        lines.append(
            f"- **{r['id']}** — status={r['status']}, "
            f"prompt={r['prompt_tokens']}, completion={r['completion_tokens']}, "
            f"total={r['total_tokens']} tokens, "
            f"est. ${r['estimated_cost_usd']:.6f}"
        )
    lines.append("")

    return ("\n".join(lines) + "\n").encode("utf-8")


def _esc(text) -> str:
    """Escape for reportlab Paragraph mini-HTML."""
    s = "" if text is None else str(text)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def render_pdf(dossier: dict) -> bytes:
    eng = dossier["engagement"]
    scope = dossier.get("scope")
    findings = dossier.get("findings", [])
    cost = dossier.get("cost_totals", {})
    summary = dossier.get("summary", {})

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="Mono",
            parent=styles["Code"],
            fontSize=8,
            leading=10,
            alignment=TA_LEFT,
        )
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        title=f"Engagement Dossier — {eng['name']}",
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    flow: list = []

    def para(text: str, style: str = "BodyText") -> None:
        flow.append(Paragraph(text, styles[style]))

    para(f"Engagement Dossier — {_esc(eng['name'])}", "Title")
    para(f"Generated: {_esc(dossier.get('generated_at', ''))}", "Italic")
    flow.append(Spacer(1, 6 * mm))

    para("Engagement", "Heading2")
    for label, key in (
        ("ID", "id"),
        ("Name", "name"),
        ("Target type", "target_type"),
        ("Target", "target_ref"),
        ("Status", "status"),
        ("Created", "created_at"),
    ):
        para(f"<b>{label}:</b> {_esc(eng.get(key, ''))}")
    flow.append(Spacer(1, 4 * mm))

    para("Authorization / Scope", "Heading2")
    if scope is None:
        para("No scope/authorization record on file.")
    else:
        para(f"<b>Authorized by:</b> {_esc(scope['authorized_by'])}")
        para(
            f"<b>Non-destructive only:</b> {_esc(scope['non_destructive_only'])}"
        )
        para("<b>Authorized targets:</b>")
        items = [
            ListItem(Paragraph(_esc(t), styles["BodyText"]))
            for t in scope.get("authorized_targets", [])
        ]
        if items:
            flow.append(ListFlowable(items, bulletType="bullet"))
        para(f"<b>Rules of engagement:</b> {_esc(scope['rules_of_engagement'])}")
    flow.append(Spacer(1, 4 * mm))

    para("Summary", "Heading2")
    para(f"<b>Total findings:</b> {summary.get('finding_count', 0)}")
    for sev, n in (summary.get("severity_counts") or {}).items():
        para(f"{_esc(sev)}: {n}")
    para(f"<b>Cost totals:</b> {_esc(_fmt_cost(cost))}")
    flow.append(Spacer(1, 4 * mm))

    para("Findings", "Heading2")
    if not findings:
        para("No findings recorded for this engagement.")
    for i, f in enumerate(findings, start=1):
        cvss = f.get("cvss_score")
        cvss_str = f"{cvss}" if cvss is not None else "n/a"
        para(
            f"{i}. [{_esc((f['severity_label'] or '').upper())}] {_esc(f['title'])}",
            "Heading3",
        )
        para(f"<b>Severity:</b> {_esc(f['severity_label'])} &nbsp; "
             f"<b>CVSS:</b> {_esc(cvss_str)} &nbsp; "
             f"<b>Confidence:</b> {_esc(f['confidence'])}")
        para(f"<b>Category:</b> {_esc(f['category'])} &nbsp; "
             f"<b>Status:</b> {_esc(f['status'])}")
        para(f"<b>Location:</b> {_esc(f['location'])}")
        para(f"<b>Description:</b> {_esc(f['description'])}")
        para("<b>Evidence / PoC:</b>")
        para(_esc(f.get("evidence", "") or ""), "Mono")
        para(f"<b>Remediation:</b> {_esc(f['remediation'])}")
        if f.get("suggested_patch"):
            para("<b>Suggested patch:</b>")
            para(_esc(f["suggested_patch"]), "Mono")
        flow.append(Spacer(1, 3 * mm))

    para("Runs", "Heading2")
    if not dossier.get("runs"):
        para("No assessment runs recorded.")
    for r in dossier.get("runs", []):
        para(
            f"<b>{_esc(r['id'])}</b> — status={_esc(r['status'])}, "
            f"total={r['total_tokens']} tokens, "
            f"est. ${r['estimated_cost_usd']:.6f}"
        )

    doc.build(flow)
    return buf.getvalue()

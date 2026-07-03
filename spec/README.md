# Spec — Single Source of Truth

This directory is the authoritative specification for the **Data Analyst Agent**. All code must match this spec. When spec and code disagree, spec wins — fix the code.

## Vision

A single-user, browser-based data-analyst agent for ad-hoc exploration. The user uploads a small tabular file (a few MB) and asks plain-English questions. The agent auto-profiles the data on upload, then answers each question by **writing real pandas code, running it locally against the actual dataframe, and self-correcting on error** — returning the key numbers, a brief note on how it got there, and an auto-generated chart when one fits. Trust bar is high (the user acts on the numbers), so shown-work and correctness are prioritized over speed; LLM cost is kept low via a cheap-but-capable model tier and minimal prompt payloads.

The running conversation stays in view. Sessions are essentially one-shot (upload → ask → answer) but the history of Q&A remains visible.

## Capability Index

See [capabilities/index.md](capabilities/index.md). Core capabilities (Phase 1):
1. Upload & auto-profile dataset
2. Ask question → codegen → local execute → self-correct → answer with method note
3. Auto-chart when it fits
4. Per-question transparency: shown code + token count + step status + query log

## Manifest

```
roadmap.md       ← Purpose, success criteria, out-of-scope, phased plan
architecture.md  ← System design, trust boundary, and the chosen ## Stack
agent.md         ← The LangGraph agent (state, nodes, edges, retry loop)
data.md          ← SQLAlchemy models + query log file
api.md           ← REST endpoints and response envelope
ui.md            ← Single-page UI + labelled stubs
capabilities/    ← One file per capability
```

## Governance Rules

1. **Spec first** — no code change without a spec backing it
2. **One fact, one place** — cross-reference with links, never duplicate facts
3. **Capabilities are atomic** — one discrete behaviour per file
4. **WHAT here, HOW in architecture.md / agent.md** — no stack detail leaks into the product-narrative files

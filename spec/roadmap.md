# Roadmap — DealScout

---

## What This Agent Does

DealScout is a personal, browser-based AI shopping assistant for a single user researching purchases across popular Indian shopping sites (Amazon.in, Flipkart, Myntra/Ajio, quick-commerce, and electronics retailers). The user asks one self-contained question — starting with a product name — and DealScout runs a deep, multi-step web-grounded research pass, cross-checks prices and reviews across sites, and returns a **ranked list of 3–5 deals**, each with the site, the price, and a one-line reason why it ranks where it does. Accuracy is prioritised over speed: a thorough answer in ~30–90s is acceptable, and the user acts on the ranking directly.

## Who Uses It

A single individual shopper (the owner of the deployment) researching a specific purchase. They are price- and value-sensitive, shop across multiple Indian sites, and want a trustworthy shortlist rather than a wall of search results. They interact through a browser web UI on their own machine.

## Core Problem Being Solved

Manually comparing a product across Amazon.in, Flipkart, Myntra/Ajio, quick-commerce, and electronics sites — opening tabs, reading reviews, checking whether a "discount" is genuine — is slow and error-prone. DealScout automates that research and returns a decision-ready ranked shortlist with reasons, so the user can act in one glance instead of an hour of tab-juggling.

## Success Criteria

- [ ] For a clear product-name query, DealScout returns a ranked list of 3–5 deals, each with a site, a price (in INR), and a one-line reason, within ~30–90s.
- [ ] Every ranked entry cites a real listing surfaced via Gemini's Google Search grounding — no fabricated prices or sites (grounding metadata is present for the run).
- [ ] During the research run the UI shows named progress steps ("Searching Indian shopping sites…", "Reading reviews & cross-checking prices…", "Ranking deals…"), reflecting real work.
- [ ] After each answer the UI shows the tokens used and estimated cost (INR) for that query.
- [ ] Each query is fully independent — no history, preferences, or conversation memory influence the result (statelessness is observable: identical inputs produce independently-derived results).

## What This Agent Does NOT Do (Out of Scope)

- **No memory of any kind** — no saved history, no saved preferences, no conversation/turn memory. Every query is independent and stateless.
- **No multi-user / auth / accounts** — single-user personal tool only.
- **No purchasing / cart / checkout** — DealScout researches and ranks; the user buys manually.
- **No price-tracking, alerts, or scheduled runs** — it answers on demand only.
- **No non-Indian marketplaces** — scope is Indian shopping sites.
- **No forced reasoning dump** — the output is the clean ranked list + one-line reasons, not a chain-of-thought transcript.

## Key Constraints

- **Latency:** ~30–90s per query is acceptable; accuracy is prioritised over speed.
- **LLM:** Gemini only, via `AGENT_GEMINI_API_KEY`, using the **native Google Search grounding tool** (`google_search`) for all web research. No third-party scraping or search APIs.
- **Cost/exposure:** send only trimmed, relevant content to the LLM; report tokens/cost per query.
- **Quality bar:** the user acts on the ranking directly, so ranked entries must be grounded and defensible.
- **Stack is fixed:** Python + FastAPI + LangGraph + SQLite backend (extend the `transform_text` slot in place — do not rename/copy the package); Next.js static-exported UI served at `:8001/app/`. See [`architecture.md`](architecture.md#stack).

---

## Phases of Development

> **Phase 1 is the smallest first-time-right user-testable win.** Real Gemini + Google Search grounding on the one core path (product-name → ranked deals), with clearly-labelled non-functional stubs for later features. Phase 2 wires every stub into a real feature.

### Phase 1 — Product-name research → ranked deals

- **Goal:** The user types a **product name** in the web UI, DealScout runs a real Gemini-grounded research pass across Indian shopping sites, and returns a ranked list of 3–5 deals — each with price, site, and a one-line reason — with named-step progress shown during the run and tokens/cost shown after. Real backend on this path; all other input modes and the deal-quality flag are visible, labelled, non-functional stubs.
- **Capabilities delivered:** [product-name-search](capabilities/product-name-search.md), [ranked-deal-list](capabilities/ranked-deal-list.md), [research-progress](capabilities/research-progress.md), [cost-report](capabilities/cost-report.md).
- **Independent slices (parallel build units):**
  - `backend` (backend, `src/`) — deps: none. Extends the `transform_text` slot into the DealScout research graph: state, nodes (research → rank), prompts, Gemini grounding + usage/cost extraction, background run execution, progress + deals + usage persistence, API routes, DB model + migration, integration test. Contract for the frontend is defined in [`api.md`](api.md) so the frontend builds concurrently without touching `src/`.
  - `frontend` (frontend, `frontend/`) — deps: none (builds against the [`api.md`](api.md) contract). Replaces the transform form with the product-name search box, the polling progress bar with named steps, the ranked-deal list, the token/cost footer, and clearly-labelled non-functional stubs (URL input, category exploration, clarifying-question, deal-quality flag). Playwright E2E smoke.
- **Key surfaces / files:**
  - backend: `src/graph/state.py`, `src/graph/nodes.py`, `src/graph/edges.py`, `src/graph/agent.py`, `src/graph/runner.py`, `src/prompts/research.md`, `src/prompts/rank.md`, `src/llm/providers/gemini.py`, `src/tools/pricing.py`, `src/db/models.py`, `src/domain/deal.py`, `src/domain/run.py`, `src/api/runs.py`, `alembic/versions/`, `tests/integration/test_deal_research.py`, `tests/unit/graph/`
  - frontend: `frontend/src/app/page.tsx`, `frontend/src/components/*`, `frontend/tests/e2e/deal-search.spec.ts`
- **Gate command:** `uv run alembic upgrade head && uv run alembic current && uv run pytest tests/integration/test_deal_research.py tests/unit -q` (real Gemini via `AGENT_GEMINI_API_KEY` in `.env`, real SQLite via `AGENT_DATABASE_URL`), followed by the built-UI E2E: `cd frontend && pnpm build && pnpm exec playwright test tests/e2e/deal-search.spec.ts` against the live app at `http://localhost:8001/app/`.
- **How the user tests it (handoff seed):**
  1. Ensure `.env` has `AGENT_GEMINI_API_KEY` and `AGENT_DATABASE_URL=sqlite:///./data/agent.db`.
  2. `uv run alembic upgrade head` then `uv run python -m src` (serves API + built UI on `:8001`).
  3. Open `http://localhost:8001/app/`, type a product name (e.g. "Sony WH-1000XM5 headphones"), click **Find deals**.
  4. Watch the progress bar advance through named steps for ~30–90s.
  5. Expected: a ranked list of 3–5 deals, each showing site + price (INR) + a one-line reason, and a footer showing tokens used + estimated cost (INR).
  6. **Labelled stubs (not bugs):** the "Paste a product URL", "Explore a category", clarifying-question prompt, and "deal-quality flag" badges are visibly greyed/tagged "Coming soon" and do nothing yet.

### Phase 2 — URL & category research + clarify gate + deal-quality flag

- **Goal:** Turn every Phase-1 stub into a real feature: research by pasted **product URL**, **category exploration**, a **clarifying-question gate** that pauses and asks ONE question when input is ambiguous, and **deal-quality flagging** (is the discount genuine / a good time to buy). After this phase every capability in the spec is real.
- **Capabilities delivered (4):** [url-input-research](capabilities/url-input-research.md), [category-exploration](capabilities/category-exploration.md), [clarifying-question-gate](capabilities/clarifying-question-gate.md), [deal-quality-flag](capabilities/deal-quality-flag.md).
- **Independent slices (parallel build units):**
  - `backend` (backend, `src/`) — deps: none (extends Phase-1 graph). Adds query-type routing (name/url/category), a clarify node + conditional pause edge, a deal-quality assessment node/tool, prompts, state fields, API support for resuming a paused run with an answer, and integration tests per mode.
  - `frontend` (frontend, `frontend/`) — deps: none (builds against extended [`api.md`](api.md) contract). Activates the URL input, category explorer, the clarifying-question prompt UI (single question → answer → resume), and the deal-quality badge; removes the "Coming soon" labels. Extends Playwright E2E.
- **Key surfaces / files:**
  - backend: `src/graph/state.py`, `src/graph/nodes.py`, `src/graph/edges.py`, `src/graph/agent.py`, `src/prompts/clarify.md`, `src/prompts/deal_quality.md`, `src/tools/deal_quality.py`, `src/api/runs.py`, `tests/integration/test_url_research.py`, `tests/integration/test_category.py`, `tests/integration/test_clarify.py`, `tests/integration/test_deal_quality.py`
  - frontend: `frontend/src/app/page.tsx`, `frontend/src/components/*`, `frontend/tests/e2e/*.spec.ts`
- **Gate command:** `uv run pytest tests/integration -q` (real Gemini via `.env`, real SQLite), followed by `cd frontend && pnpm build && pnpm exec playwright test` against the live app at `http://localhost:8001/app/`.
- **How the user tests it (handoff seed):**
  1. `uv run python -m src`, open `http://localhost:8001/app/`.
  2. **URL mode:** paste an Amazon.in/Flipkart product URL → expect a ranked list built around that item across sites.
  3. **Category mode:** enter a category (e.g. "wireless earbuds under ₹5000") → expect best-deal picks for the category.
  4. **Clarify gate:** enter a deliberately ambiguous query (e.g. "good phone") → expect DealScout to pause and ask ONE clarifying question before researching; answer it → research proceeds.
  5. **Deal-quality:** each ranked entry shows a deal-quality badge (e.g. "Genuine discount" / "Wait — usually cheaper") with a one-line justification.
  6. No stubs remain; every surface is live.

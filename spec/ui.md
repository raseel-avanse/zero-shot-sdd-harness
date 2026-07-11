# UI — DealScout

A single-page Next.js 15 / React 19 app, statically exported and served at `:8001/app/`. One screen, single primary action. Clean, honest, decision-focused: the output is the ranked list, nothing more.

## Screen: Deal Search (single page)

### Layout (top → bottom)
1. **Header** — "DealScout" title + one-line tagline ("Find the best deal across Indian shopping sites").
2. **Query input area**
   - **Product name** search box + **Find deals** primary button (P1, real).
   - **Mode tabs / secondary inputs** for **Paste a product URL** and **Explore a category** — **Phase 1: rendered but disabled, tagged "Coming soon"** (labelled stubs, never mistaken for bugs). **Phase 2: activated.**
3. **Progress area** (visible while `status=running`)
   - Named-step progress bar reflecting `progress_step`: "Searching Indian shopping sites…" → "Reading reviews & cross-checking prices…" → "Ranking deals…" → (P2) "Checking deal quality…". Polls `GET /runs/{id}` (~1s). Progress reflects real backend work, never faked.
4. **Clarify prompt** (P2, `status=needs_input`) — a single question with a one-line answer field + "Continue" button. Phase 1: not rendered (or a disabled "Coming soon" hint).
5. **Results area** (`status=completed`)
   - Ranked list of 3–5 **deal cards**: rank badge, site, price (₹, formatted INR), one-line reason. (P2) a **deal-quality badge** ("Genuine discount" / "Wait — usually cheaper" / "Unknown") + its one-line justification. Phase 1: the badge slot renders a disabled "Coming soon" chip.
6. **Cost footer** (`status=completed`) — "This query used N tokens · approx ₹X.XX".

### The four states (all designed)
- **Empty** (no query yet): centered guidance — "Type a product name to find the best deals across Indian shopping sites." Primary button visible.
- **Loading** (`running`): the named-step progress bar with contextual labels; input disabled; button shows "Finding deals…".
- **Error** (`failed` or network): human message — "Couldn't reach the research service — try again." with a Retry action. Never a stack trace.
- **Ideal** (`completed`): the ranked deal cards + cost footer. Empty grounding → "No confident deals found for that — try a more specific name."

### Interaction & quality
- Feedback within ~100ms: button disables + progress area appears on submit.
- One clear primary action (Find deals); secondary inputs visibly secondary/disabled when stubbed.
- Accessible: real `<button>`, `<label>`-linked `<input>`, keyboard-reachable, visible focus ring, WCAG AA contrast; respects `prefers-reduced-motion`.
- Prices formatted as INR (`₹24,990`). No dual-representation — each value shown once.

## Labelled stubs (Phase 1)
| Surface | Phase 1 state | Becomes real in |
|---------|---------------|-----------------|
| Paste-a-URL input | disabled + "Coming soon" tag | Phase 2 |
| Explore-a-category input | disabled + "Coming soon" tag | Phase 2 |
| Clarifying-question prompt | not shown / disabled hint | Phase 2 |
| Deal-quality badge | disabled "Coming soon" chip on each card | Phase 2 |

## E2E (Playwright, `frontend/tests/e2e/`)
Phase 1 smoke against the live app at `http://localhost:8001/app/`: type a product name → submit → assert progress bar appears with a named step → wait for completion → assert ≥3 ranked deal cards each showing a site, an INR price, and a reason → assert the cost footer shows tokens + INR. Asserts real rendered output, not just HTTP 200.

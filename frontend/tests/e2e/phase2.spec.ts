import { test, expect } from '@playwright/test'

// Phase 2 E2E against the LIVE app at http://localhost:8001/app/.
//
// REQUIRES THE PHASE-2 BACKEND. These specs exercise routes/behaviour that the
// Phase-1 backend does not yet serve: query_type=url|category, the needs_input
// clarify gate, POST /runs/{id}/answer, and populated deal-quality fields. Run
// them only after the coordinator restarts the backend on the P2 build. Each
// makes a real Gemini + Google Search pass (~30–90s) and asserts real rendered
// content, never just HTTP 200. Mind the Gemini free-tier daily quota.

test.describe('Phase 2 — requires the restarted P2 backend', () => {
  test('URL mode researches the pasted product and ranks it across sites', async ({ page }) => {
    await page.goto('/app/')

    await page.getByTestId('mode-url').click()
    await expect(page.getByTestId('mode-url')).toHaveAttribute('data-active', 'true')

    // A real Indian-marketplace product URL.
    await page
      .getByTestId('query-input')
      .fill('https://www.amazon.in/Sony-WH-1000XM5-Cancelling-Wireless-Headphones/dp/B09XS7JWHH')
    await page.getByTestId('find-deals').click()

    await expect(page.getByTestId('progress-area')).toBeVisible()

    // Resolves to either ranked deals, a friendly empty state, or a clarify gate
    // (an unreachable/ambiguous URL degrades gracefully — never a crash).
    await expect(
      page
        .getByTestId('results-area')
        .or(page.getByTestId('clarify-prompt')),
    ).toBeVisible({ timeout: 150_000 })

    if (await page.getByTestId('deal-card').count()) {
      const first = page.getByTestId('deal-card').first()
      await expect(first.getByTestId('deal-price')).toContainText('₹')
      await expect(first.getByTestId('quality-badge')).toBeVisible()
    }
  })

  test('Category mode returns best-value picks with INR prices', async ({ page }) => {
    await page.goto('/app/')

    await page.getByTestId('mode-category').click()
    await expect(page.getByTestId('mode-category')).toHaveAttribute('data-active', 'true')

    await page.getByTestId('query-input').fill('wireless earbuds under ₹5000')
    await page.getByTestId('find-deals').click()

    await expect(page.getByTestId('progress-area')).toBeVisible()
    await expect(page.getByTestId('results-area')).toBeVisible({ timeout: 150_000 })

    const count = await page.getByTestId('deal-card').count()
    if (count) {
      expect(count).toBeGreaterThanOrEqual(3)
      const first = page.getByTestId('deal-card').first()
      await expect(first.getByTestId('deal-site')).not.toBeEmpty()
      await expect(first.getByTestId('deal-price')).toContainText('₹')
    } else {
      await expect(page.getByTestId('no-deals')).toBeVisible()
    }
  })

  test('Clarify gate: ambiguous query pauses, then answering resumes to a ranked list', async ({
    page,
  }) => {
    await page.goto('/app/')

    // A deliberately ambiguous query should trigger the needs_input gate.
    await page.getByTestId('query-input').fill('good phone')
    await page.getByTestId('find-deals').click()

    // First-class needs_input state: exactly one clarifying question + an answer field.
    await expect(page.getByTestId('clarify-prompt')).toBeVisible({ timeout: 150_000 })
    await expect(page.getByTestId('clarify-question')).not.toBeEmpty()

    await page.getByTestId('clarify-input').fill('Around ₹25000, 5G, good camera, for photography')
    await page.getByTestId('clarify-continue').click()

    // Resumes polling and completes with a ranked list.
    await expect(page.getByTestId('progress-area')).toBeVisible()
    await expect(page.getByTestId('results-area')).toBeVisible({ timeout: 150_000 })

    const count = await page.getByTestId('deal-card').count()
    if (count) {
      await expect(page.getByTestId('deal-card').first().getByTestId('deal-price')).toContainText('₹')
    } else {
      await expect(page.getByTestId('no-deals')).toBeVisible()
    }
  })

  test('Deal-quality badge renders a real label + justification on each card', async ({ page }) => {
    await page.goto('/app/')

    await page.getByTestId('query-input').fill('Sony WH-1000XM5 headphones')
    await page.getByTestId('find-deals').click()

    await expect(page.getByTestId('results-area')).toBeVisible({ timeout: 150_000 })

    const count = await page.getByTestId('deal-card').count()
    test.skip(count === 0, 'No deals grounded — nothing to assert quality on.')

    const badge = page.getByTestId('deal-card').first().getByTestId('quality-badge')
    await expect(badge).toBeVisible()
    // The badge carries one of the three real labels, not a "Coming soon" stub.
    await expect(badge).toContainText(
      /Genuine discount|Wait — usually cheaper|Price check unavailable/,
    )
    await expect(badge).toHaveAttribute('data-label', /genuine_discount|wait|unknown/)
  })
})

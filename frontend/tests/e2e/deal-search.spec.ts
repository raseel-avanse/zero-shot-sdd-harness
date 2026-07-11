import { test, expect } from '@playwright/test'

// Phase 1 golden-path smoke against the LIVE app at http://localhost:8001/app/.
// The backend runs a real Gemini + Google Search grounding pass (~30–90s), so
// this asserts on REAL rendered content, never just an HTTP 200.

test('product-name search returns a ranked deal list with a cost footer', async ({ page }) => {
  await page.goto('/')

  // Page loads and is styled: the header + primary action are present.
  await expect(page.getByRole('heading', { name: 'DealScout' })).toBeVisible()
  await expect(page.getByTestId('empty-state')).toBeVisible()

  // Labelled stubs are visible but disabled (must not read as bugs).
  await expect(page.getByTestId('stub-url')).toBeDisabled()
  await expect(page.getByTestId('stub-category')).toBeDisabled()

  // Primary interaction: type a product name and submit.
  await page.getByTestId('query-input').fill('Sony WH-1000XM5 headphones')
  await page.getByTestId('find-deals').click()

  // The named-step progress bar appears (real backend work, not a spinner).
  await expect(page.getByTestId('progress-area')).toBeVisible()
  await expect(page.getByTestId('progress-label')).toContainText(/Searching|Reading|Ranking/)

  // Wait for the run to complete and the ranked list to render.
  await expect(page.getByTestId('results-area')).toBeVisible({ timeout: 150_000 })

  const cards = page.getByTestId('deal-card')
  const count = await cards.count()

  if (count === 0) {
    // Empty grounding is a valid completed outcome — friendly message, not error.
    await expect(page.getByTestId('no-deals')).toBeVisible()
  } else {
    expect(count).toBeGreaterThanOrEqual(3)
    // First card carries real content: a site, an INR price, and a reason.
    const first = cards.first()
    await expect(first.getByTestId('deal-site')).not.toBeEmpty()
    await expect(first.getByTestId('deal-price')).toContainText('₹')
    await expect(first.getByTestId('deal-reason')).not.toBeEmpty()
  }

  // Cost footer shows tokens (+ INR) after completion.
  const footer = page.getByTestId('cost-footer')
  await expect(footer).toBeVisible()
  await expect(footer).toContainText('tokens')
})

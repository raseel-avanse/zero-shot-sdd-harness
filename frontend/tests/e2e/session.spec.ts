import { test, expect } from '@playwright/test'
import path from 'node:path'

const FIXTURE = path.join(__dirname, 'sales.csv')

// Generous per-answer wait: each ask is a real Gemini round-trip.
const ANSWER_TIMEOUT = 90_000

test('golden path: upload, ask with shown work, chart, persist, follow-up context', async ({ page }) => {
  await page.goto('./')

  // Page renders and is styled (heading visible, real layout — not a blank page).
  const heading = page.getByRole('heading', { name: 'Data Analyst Agent' })
  await expect(heading).toBeVisible()
  // Tailwind is applied: the heading has a computed font-weight heavier than normal.
  const fontWeight = await heading.evaluate(el => getComputedStyle(el).fontWeight)
  expect(Number(fontWeight)).toBeGreaterThanOrEqual(600)

  // At least one stub button is present and disabled ("Coming soon" — a future feature, not a bug).
  const stubs = page.getByTestId('stub-button')
  await expect(stubs.first()).toBeVisible()
  await expect(stubs.first()).toBeDisabled()

  // Upload the fixture CSV; the profile appears (creates a fresh session, local profiling).
  await page.getByTestId('file-input').setInputFiles(FIXTURE)
  const profile = page.getByTestId('profile-card')
  await expect(profile).toBeVisible({ timeout: 30_000 })
  // Profile card shows the row count (fixture has 12 data rows).
  await expect(page.getByTestId('row-count')).toContainText('12 rows')

  // --- ASK 1: factual question — assert real content + token badge + shown pandas. ---
  await page.getByTestId('question-input').fill('What is the average revenue per region?')
  await page.getByTestId('ask-button').click()

  const firstAnswer = page.getByTestId('answer-text').first()
  await expect(firstAnswer).toBeVisible({ timeout: ANSWER_TIMEOUT })
  await expect(firstAnswer).not.toBeEmpty()

  // Token-count badge shows a real total on the answer.
  const tokenBadge = page.getByTestId('token-badge').first()
  await expect(tokenBadge).toBeVisible()
  await expect(tokenBadge).toContainText('tokens')

  // "Show code" reveals executed pandas code that references the dataframe.
  await page.getByTestId('show-code-toggle').first().click()
  const code = page.getByTestId('executed-code').first()
  await expect(code).toBeVisible()
  await expect(code).toContainText('df')

  // --- ASK 2: another factual question (builds session history). ---
  {
    const before = await page.getByTestId('answer-card').count()
    await page.getByTestId('question-input').fill('How many rows are in the dataset?')
    await page.getByTestId('ask-button').click()
    await expect
      .poll(async () => page.getByTestId('answer-card').count(), { timeout: ANSWER_TIMEOUT })
      .toBe(before + 1)
    await expect(page.getByTestId('answer-text').first()).not.toBeEmpty()
  }

  // --- ASK 3: chart-worthy question (auto-chart proven across the session below). ---
  {
    const before = await page.getByTestId('answer-card').count()
    await page.getByTestId('question-input').fill('Show total revenue per region.')
    await page.getByTestId('ask-button').click()
    await expect
      .poll(async () => page.getByTestId('answer-card').count(), { timeout: ANSWER_TIMEOUT })
      .toBe(before + 1)
    await expect(page.getByTestId('answer-text').first()).not.toBeEmpty()
  }

  // Three answered turns are shown.
  await expect(page.getByTestId('answer-card')).toHaveCount(3)

  // RELOAD — history must be restored from the server (persistence proof).
  await page.reload()
  await expect(page.getByTestId('profile-card')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByTestId('answer-card')).toHaveCount(3, { timeout: 30_000 })
  // Each restored question text is present.
  const restored = [
    'What is the average revenue per region?',
    'How many rows are in the dataset?',
    'Show total revenue per region.',
  ]
  for (const q of restored) {
    await expect(page.getByTestId('answer-question').filter({ hasText: q })).toBeVisible()
  }

  // FOLLOW-UP referencing prior context; a new turn appears with real content.
  await page.getByTestId('question-input').fill('Now break that down by region.')
  await page.getByTestId('ask-button').click()
  await expect
    .poll(async () => page.getByTestId('answer-card').count(), { timeout: ANSWER_TIMEOUT })
    .toBe(4)
  await expect(page.getByTestId('answer-text').first()).not.toBeEmpty()

  // AUTO-CHART: at least one recharts <svg> chart renders somewhere in the
  // conversation. Two chart-worthy questions were asked ("total revenue per
  // region" and the "break that down by region" follow-up); the agent renders a
  // chart when one fits. We assert on the whole session rather than a single
  // turn so the proof does not hinge on which turn the model chose to chart.
  const charts = page.getByTestId('chart').locator('svg')
  await expect
    .poll(async () => charts.count(), { timeout: 60_000 })
    .toBeGreaterThan(0)
  await expect(charts.first()).toBeVisible()

  // The session picker lists the active session as data-loaded.
  const item = page.getByTestId('session-item').first()
  await expect(item).toBeVisible()
  await expect(item.getByTestId('session-loaded-indicator')).toContainText('data loaded')
})

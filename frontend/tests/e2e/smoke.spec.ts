import { test, expect } from '@playwright/test'
import path from 'node:path'

const FIXTURE = path.join(__dirname, 'sales.csv')

test('upload a CSV, profile it, ask a question, and read the shown-work answer', async ({ page }) => {
  await page.goto('./')

  // Page renders and is styled (heading visible, real layout — not a blank page).
  const heading = page.getByRole('heading', { name: 'Data Analyst Agent' })
  await expect(heading).toBeVisible()
  // Tailwind is applied: the heading has a computed font-weight heavier than normal.
  const fontWeight = await heading.evaluate(el => getComputedStyle(el).fontWeight)
  expect(Number(fontWeight)).toBeGreaterThanOrEqual(600)

  // Stubs are present and disabled (future features, not bugs).
  const stubs = page.getByTestId('stub-button')
  await expect(stubs.first()).toBeVisible()
  await expect(stubs.first()).toBeDisabled()

  // Upload the fixture CSV.
  await page.getByTestId('file-input').setInputFiles(FIXTURE)

  // Profile card shows the row count (fixture has 12 data rows).
  const profile = page.getByTestId('profile-card')
  await expect(profile).toBeVisible({ timeout: 30_000 })
  await expect(page.getByTestId('row-count')).toContainText('12 rows')

  // Ask a factual question and submit.
  await page.getByTestId('question-input').fill('What is the average revenue per region?')
  await page.getByTestId('ask-button').click()

  // An answer card appears; the answer text is real (non-empty).
  const answer = page.getByTestId('answer-text')
  await expect(answer).toBeVisible({ timeout: 90_000 })
  await expect(answer).not.toBeEmpty()

  // Token-count badge shows a real total.
  const tokenBadge = page.getByTestId('token-badge').first()
  await expect(tokenBadge).toBeVisible()
  await expect(tokenBadge).toContainText('tokens')

  // "Show code" reveals executed pandas code that references the dataframe.
  await page.getByTestId('show-code-toggle').first().click()
  const code = page.getByTestId('executed-code').first()
  await expect(code).toBeVisible()
  await expect(code).toContainText('df')
})

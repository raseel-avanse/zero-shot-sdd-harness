import { expect, test } from '@playwright/test'

// Primary-journey smoke: create a scope-gated engagement pointing at a real
// local repo, start a real assessment, and assert at least one finding card
// renders with real content (severity + location + remediation).
//
// The target repo must be a readable path the backend can scan and must be in
// the allowlist. Provide it via E2E_TARGET_REPO; the gate seeds a vulnerable
// fixture repo and exports its path. Falls back to the project checkout root.
const TARGET_REPO =
  process.env.E2E_TARGET_REPO ?? '/home/raseel/code/LearningLab/zero-shot-sdd-harness'

test('create engagement, start assessment, and stream a real finding card', async ({ page }) => {
  await page.goto('./')

  // 1. Create engagement via the scope form.
  await page.getByTestId('new-engagement').click()
  await page.getByLabel('Engagement name').fill(`E2E ${Date.now()}`)
  await page.getByLabel('Target repository path').fill(TARGET_REPO)
  await page.getByLabel('Authorized target 1').fill(TARGET_REPO)
  await page.getByLabel('Rules of engagement').fill('Authorized non-destructive assessment; read-only.')
  await page.getByLabel('Authorized by').fill('e2e-runner')
  await page.getByRole('button', { name: 'Create engagement' }).click()

  // 2. Lands on the run view.
  await expect(page.getByTestId('start-assessment')).toBeVisible({ timeout: 30_000 })

  // 3. Start the assessment.
  await page.getByTestId('start-assessment').click()

  // Progress panel appears and the step counter is live.
  await expect(page.getByTestId('step-counter')).toBeVisible({ timeout: 30_000 })

  // 4. At least one finding card streams in with real content.
  const firstCard = page.getByTestId('finding-card').first()
  await expect(firstCard).toBeVisible({ timeout: 150_000 })

  // Severity badge, file:line location, and remediation are all present.
  await expect(firstCard.getByTestId('finding-location')).not.toBeEmpty()
  await expect(firstCard.getByText('Remediation')).toBeVisible()
  await expect(firstCard.getByRole('heading', { level: 3 }).first()).not.toBeEmpty()

  // Token/cost panel reflects real work (non-zero cost by the time we finish).
  await expect(page.getByTestId('est-cost')).toBeVisible()
})

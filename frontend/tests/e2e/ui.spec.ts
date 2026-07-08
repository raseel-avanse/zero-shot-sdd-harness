import { expect, test } from '@playwright/test'

// UI-surface smoke tests — do not depend on a real assessment producing
// findings. They assert the app loads styled, is interactive, and that the
// scope form + labelled stubs render correctly.

test('app loads, is styled, and shows the Sentinel console', async ({ page }) => {
  await page.goto('./')
  await expect(page.getByRole('heading', { name: 'Sentinel', level: 1 })).toBeVisible()

  // Styled: the dark console background must actually be applied (not unstyled).
  const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor)
  expect(bg).not.toBe('rgba(0, 0, 0, 0)')
  expect(bg).not.toBe('rgb(255, 255, 255)')

  // Either the empty state or an engagements list is present — never a blank panel.
  await expect(page.getByRole('heading', { name: 'Engagements' })).toBeVisible()
  await expect(page.getByTestId('new-engagement')).toBeVisible()
})

test('scope form renders and validates', async ({ page }) => {
  await page.goto('./')
  await page.getByTestId('new-engagement').click()

  await expect(page.getByRole('heading', { name: 'New engagement' })).toBeVisible()
  await expect(page.getByLabel('Engagement name')).toBeVisible()
  await expect(page.getByLabel('Target repository path')).toBeVisible()

  // Submitting empty surfaces inline validation, not a crash.
  await page.getByRole('button', { name: 'Create engagement' }).click()
  await expect(page.getByText('Name is required.')).toBeVisible()
})

test('live-app target type is selectable and shows the non-destructive notice (Phase 2 real)', async ({
  page,
}) => {
  await page.goto('./')
  await page.getByTestId('new-engagement').click()

  // Selecting live-app switches the target field to a base-URL input and shows
  // the read-only / non-destructive scope notice.
  await page.getByTestId('target-type-live').click()
  await expect(page.getByLabel('Target base URL')).toBeVisible()
  await expect(page.getByTestId('live-nondestructive-notice')).toContainText(/non-destructive/i)
  await expect(page.getByTestId('live-nondestructive-notice')).toContainText(/GET \/ HEAD \/ OPTIONS/i)

  // A non-URL base URL is rejected inline (in-code host guard on the backend too).
  await page.getByLabel('Engagement name').fill('Live probe')
  await page.getByLabel('Target base URL').fill('not-a-url')
  await page.getByRole('button', { name: 'Create engagement' }).click()
  await expect(page.getByText(/must start with http/i)).toBeVisible()
})

test('allowlist rows can be added and removed', async ({ page }) => {
  await page.goto('./')
  await page.getByTestId('new-engagement').click()

  await expect(page.getByLabel('Authorized target 1')).toBeVisible()
  await page.getByRole('button', { name: '+ Add path' }).click()
  await expect(page.getByLabel('Authorized target 2')).toBeVisible()
  await page.getByRole('button', { name: 'Remove path row 2' }).click()
  await expect(page.getByLabel('Authorized target 2')).toHaveCount(0)
})

// ── Phase 3 UI surfaces ────────────────────────────────────────────────────
// Create a scope-gated engagement to land on the run view, then assert the
// Phase-3 controls are now REAL (not disabled stubs): the export dossier links
// point at the export endpoint for each format, and the next-probe suggestions
// panel container renders. These do not require a completed run.

const TARGET_REPO =
  process.env.E2E_TARGET_REPO ?? '/home/raseel/code/LearningLab/zero-shot-sdd-harness'

async function createEngagement(page: import('@playwright/test').Page) {
  await page.goto('./')
  await page.getByTestId('new-engagement').click()
  await page.getByLabel('Engagement name').fill(`P3 UI ${Date.now()}`)
  await page.getByLabel('Target repository path').fill(TARGET_REPO)
  await page.getByLabel('Authorized target 1').fill(TARGET_REPO)
  await page.getByLabel('Rules of engagement').fill('Authorized non-destructive assessment; read-only.')
  await page.getByLabel('Authorized by').fill('e2e-runner')
  await page.getByRole('button', { name: 'Create engagement' }).click()
  await expect(page.getByTestId('start-assessment')).toBeVisible({ timeout: 30_000 })
}

test('export dossier controls are enabled and link to each format', async ({ page }) => {
  await createEngagement(page)

  const exportGroup = page.getByTestId('export-dossier')
  await expect(exportGroup).toBeVisible()

  for (const fmt of ['md', 'pdf', 'json'] as const) {
    const link = page.getByTestId(`export-${fmt}`)
    await expect(link).toBeVisible()
    await expect(link).toBeEnabled()
    const href = await link.getAttribute('href')
    expect(href).toMatch(new RegExp(`/engagements/[^/]+/export\\?format=${fmt}$`))
  }
})

test('next-probe suggestions panel renders on the run view', async ({ page }) => {
  await createEngagement(page)

  const panel = page.getByTestId('suggestions-panel')
  await expect(panel).toBeVisible()
  await expect(panel.getByRole('heading', { name: 'Suggested next probes' })).toBeVisible()
})

test('finding status lifecycle controls appear on a real finding card', async ({ page }) => {
  test.setTimeout(200_000)
  await createEngagement(page)

  // Run a real assessment so a finding card streams in.
  await page.getByTestId('start-assessment').click()
  await expect(page.getByTestId('step-counter')).toBeVisible({ timeout: 30_000 })

  const firstCard = page.getByTestId('finding-card').first()
  await expect(firstCard).toBeVisible({ timeout: 180_000 })

  // Lifecycle controls are present with all four statuses, and the re-test
  // control still lives alongside them.
  const controls = firstCard.getByTestId('status-controls')
  await expect(controls).toBeVisible()
  for (const s of ['new', 'validated', 'remediated', 'false_positive']) {
    await expect(controls.getByText(s.replace('_', ' '), { exact: true })).toBeVisible()
  }
  await expect(firstCard.getByTestId('retest-button')).toBeEnabled()

  // Transition to "false positive" — a status a streamed finding never starts
  // in — and confirm the active pill moves to it (persisted via PATCH).
  await firstCard.getByTestId('status-false_positive').click()
  await expect(firstCard.getByTestId('finding-status-active')).toContainText('false positive', {
    timeout: 30_000,
  })
})

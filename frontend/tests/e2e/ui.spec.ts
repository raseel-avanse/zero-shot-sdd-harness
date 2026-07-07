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

test('scope form renders, validates, and shows labelled Phase-2 stubs', async ({ page }) => {
  await page.goto('./')
  await page.getByTestId('new-engagement').click()

  await expect(page.getByRole('heading', { name: 'New engagement' })).toBeVisible()
  await expect(page.getByLabel('Engagement name')).toBeVisible()
  await expect(page.getByLabel('Target repository path')).toBeVisible()

  // Live-app target type is a clearly-labelled, disabled stub.
  await expect(page.getByText(/Coming in Phase 2/i).first()).toBeVisible()

  // Submitting empty surfaces inline validation, not a crash.
  await page.getByRole('button', { name: 'Create engagement' }).click()
  await expect(page.getByText('Name is required.')).toBeVisible()
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

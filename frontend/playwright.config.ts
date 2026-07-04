import { defineConfig, devices } from '@playwright/test'

// The backend serves the built static export at /app on port 8001.
// The orchestrator / qa-auditor starts the server; we only point at it here.
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  retries: 2,
  timeout: 180_000,
  expect: { timeout: 45_000 },
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:8001/app/',
    actionTimeout: 45_000,
    navigationTimeout: 45_000,
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})

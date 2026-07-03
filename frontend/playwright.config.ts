import { defineConfig, devices } from '@playwright/test'

// The backend serves the built static export at /app on port 8001.
// The orchestrator / qa-auditor starts the server; we only point at it here.
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:8001/app/',
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})

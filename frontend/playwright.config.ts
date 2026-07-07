import { defineConfig, devices } from '@playwright/test'

// The app is served by FastAPI at /app. The gate starts the server; these
// tests hit the live app. Override the base URL with PLAYWRIGHT_BASE_URL.
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:8001/app/'

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 180_000, // real Gemini runs can take a while to stream findings
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})

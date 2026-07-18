import { defineConfig, devices } from '@playwright/test'

// The E2E runs against the LIVE app: the backend serves the statically-exported
// UI at http://localhost:8001/app/ (single origin, real Gemini via .env).
// Start the backend separately: `uv run python -m src` after `pnpm build`.
// baseURL is the origin; specs navigate to the app path `/app/` (basePath).
const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:8001'

export default defineConfig({
  testDir: './tests/e2e',
  // A real Gemini research run takes ~30–90s; give the whole test room.
  timeout: 180_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
})

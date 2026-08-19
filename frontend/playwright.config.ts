import { defineConfig, devices } from '@playwright/test'

// Smoke-level UI-wiring tests only (see e2e/README or golden-path.spec.ts's
// header comment) - real Whisper/ffmpeg processing is out of scope here, so
// every backend call is mocked via page.route() and no real backend process
// needs to be running.
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
    // .env.development points API calls at http://localhost:8000 for local
    // dev against a real backend. Overriding it to same-origin here matches
    // how production actually serves (frontend/backend from one origin) -
    // also sidesteps a cross-origin quirk where a mocked download link's
    // `download` attribute is ignored by the browser.
    env: { VITE_API_BASE: '' },
  },
})

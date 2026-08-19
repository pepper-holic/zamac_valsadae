/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.ts'],
    globals: true,
    // e2e/ holds Playwright specs (their own test() import, own runner) -
    // Vitest's default include glob would otherwise also pick them up and
    // fail since they don't use Vitest's test API.
    exclude: ['**/node_modules/**', '**/e2e/**'],
  },
})

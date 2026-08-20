import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.SLICE1_BASE_URL || 'http://localhost';

export default defineConfig({
  testDir: './acceptance',
  timeout: 45_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [['line']],
  use: {
    baseURL,
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium-production-slice1',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});

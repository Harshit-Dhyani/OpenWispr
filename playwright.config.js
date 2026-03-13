const { defineConfig, devices } = require('@playwright/test');
const path = require('path');

module.exports = defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [['html'], ['list']],
  
  use: {
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 10000,
    navigationTimeout: 30000,
  },

  projects: [
    {
      name: 'electron',
      use: {
        ...devices['Desktop Chrome'],
        channel: 'chrome',
        launchOptions: {
          executablePath: process.env.ELECTRON_PATH || undefined,
          args: [
            path.resolve(__dirname, 'app/electron'),
            '--remote-debugging-port=9222',
          ],
          env: {
            ...process.env,
            OPENWISPR_E2E_TEST: '1',
          },
        },
      },
    },
  ],

  timeout: 120000,
});

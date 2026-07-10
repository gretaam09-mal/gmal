import { existsSync } from "node:fs";

import { defineConfig, devices } from "@playwright/test";

// Some sandboxes pre-install a Chromium build that doesn't match this
// project's pinned @playwright/test revision, at a fixed path. Prefer it
// when present; otherwise fall back to Playwright's normal browser
// resolution (as used by `playwright install` in CI).
const preinstalledChromium = "/opt/pw-browsers/chromium";
const executablePath = existsSync(preinstalledChromium) ? preinstalledChromium : undefined;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], launchOptions: { executablePath } },
    },
  ],
  webServer: {
    command: "pnpm build && pnpm start",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});

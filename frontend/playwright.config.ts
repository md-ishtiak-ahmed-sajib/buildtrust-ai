import { defineConfig } from "@playwright/test";
if (!process.env.BUILDTRUST_E2E_BASE_URL || !process.env.BUILDTRUST_E2E_CREDENTIALS)
  throw new Error("Run scripts/verify_upgrade_browser.py to create an isolated browser database and credentials.");
export default defineConfig({
  testDir: "./e2e",
  timeout: 60000,
  expect: { timeout: 10000 },
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.BUILDTRUST_E2E_BASE_URL || "http://127.0.0.1:8000",
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});

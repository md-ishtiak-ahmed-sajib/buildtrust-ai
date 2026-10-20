import { test, expect } from "./fixtures";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
import path from "node:path";

test("automated accessibility checks across application screens and review forms", async ({ page }) => {
  test.setTimeout(120000);
  const reports: { screen: string; violations: unknown[]; incomplete: unknown[] }[] = [];
  async function scan(screen: string) {
    const report = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
    reports.push({ screen, violations: report.violations, incomplete: report.incomplete });
  }
  await page.goto("/");
  await scan("login");
  const credentials = JSON.parse(fs.readFileSync(process.env.BUILDTRUST_E2E_CREDENTIALS!, "utf8"));
  await page.getByLabel("Email address").fill("admin@buildtrust.demo");
  await page.getByLabel("Password", { exact: true }).fill(credentials["admin@buildtrust.demo"]);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await expect(page.getByLabel("Select project")).toBeVisible();
  for (const screen of ["Overview", "Documents", "BOQ & Estimates", "Quantity Takeoff", "Materials & Prices", "Invoice Intelligence", "Cash-Flow Forecast", "Payment Center", "Audit & Security", "Review Inbox", "Cost Control & Accounting", "Commercial Management", "Team & Access", "Performance & Scenarios"]) {
    await page.getByRole("link", { name: screen, exact: true }).click();
    await page.waitForLoadState("networkidle");
    await scan(screen);
    if (screen === "Cost Control & Accounting" || screen === "Commercial Management") {
      await page.getByRole("button", { name: "Prepare control", exact: true }).click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await scan(`${screen} form`);
      await page.getByRole("button", { name: "Close dialog", exact: true }).click();
    }
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await scan("mobile performance");
  fs.writeFileSync(path.join(process.env.BUILDTRUST_E2E_OUTPUT!, "accessibility-results.json"), JSON.stringify({ timestamp: new Date().toISOString(), scope: "Automated WCAG tags only; incomplete checks require human assessment", reports }, null, 2));
  expect(reports.flatMap(report => report.violations.map(violation => ({ screen: report.screen, violation })))).toEqual([]);
});

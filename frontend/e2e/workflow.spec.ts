import { test, expect } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
const evidenceDir = process.env.BUILDTRUST_E2E_OUTPUT || "../data/e2e-baseline";
fs.mkdirSync(evidenceDir, { recursive: true });
const creds = JSON.parse(
  fs.readFileSync(
    path.resolve(
      process.env.BUILDTRUST_E2E_CREDENTIALS || "../data/demo-credentials.json",
    ),
    "utf8",
  ),
);
async function login(page: import("@playwright/test").Page, role: string) {
  await page.getByLabel("Email address").fill(`${role}@buildtrust.demo`);
  await page
    .getByLabel("Password", { exact: true })
    .fill(creds[`${role}@buildtrust.demo`]);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await expect(
    page.getByRole("button", { name: "Sign out", exact: true }),
  ).toBeVisible();
}
test.beforeEach(async ({ request }) => {
  const r = await request.post("/api/v1/auth/login", {
    data: {
      email: "admin@buildtrust.demo",
      password: creds["admin@buildtrust.demo"],
    },
  });
  const a = await r.json();
  expect(
    (
      await request.post("/api/v1/demo/reset", {
        headers: { Authorization: `Bearer ${a.access_token}` },
      })
    ).ok(),
  ).toBeTruthy();
});
test("review, approve, settle, receipt, and verify integrity", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await login(page, "operator");
  await expect(page.locator(".recharts-area-curve")).toBeVisible();
  await page.screenshot({
    path: path.join(evidenceDir, "01-overview.png"),
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Invoice Intelligence", exact: true })
    .click();
  await expect(
    page.getByText("1,050,000.00", { exact: false }).first(),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(evidenceDir, "02-inflated-invoice.png"),
    fullPage: true,
  });
  await page.locator('.comparison-table').screenshot({path:path.join(evidenceDir,'08-four-way-focus.png')});
  await page.getByRole("button", { name: /INV-CEMENT-070/ }).click();
  await page.getByRole("button", { name: "Run financial workflow" }).click();
  await expect(
    page.getByRole("link", { name: "Open prepared payment" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Open prepared payment" }).click();
  await expect(
    page.getByRole("button", { name: "Approve payment", exact: true }),
  ).toHaveCount(0);
  await page.screenshot({
    path: path.join(evidenceDir, "03-pending-payment.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "manager");
  await page.getByRole("link", { name: "Payment Center", exact: true }).click();
  await page
    .getByRole("button", { name: "Approve payment", exact: true })
    .click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Execute simulation" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Execute simulation" }).click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "Simulated payment receipt" }),
  ).toBeVisible();
  await expect(page.getByText("930,000.00", { exact: false })).toBeVisible();
  await page.screenshot({
    path: path.join(evidenceDir, "04-mock-receipt.png"),
  });
  await page.getByRole('dialog',{name:'Simulated payment receipt'}).screenshot({path:path.join(evidenceDir,'09-receipt-focus.png')});
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page
    .getByRole("link", { name: "Cash-Flow Forecast", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "30-day liquidity scenarios" }),
  ).toBeVisible();
  await expect(page.locator(".recharts-line-curve").first()).toBeVisible();
  await page.screenshot({
    path: path.join(evidenceDir, "05-cashflow.png"),
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Audit & Security", exact: true })
    .click();
  await page.getByRole("button", { name: "Verify audit chain" }).click();
  await expect(page.getByText("Chain verified", { exact: true })).toBeVisible();
  await page.screenshot({
    path: path.join(evidenceDir, "06-audit.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
test("upload content and responsive document review", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await login(page, "operator");
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByRole("link", { name: "Documents", exact: true }).click();
  await page
    .getByLabel("Upload financial document")
    .setInputFiles("../demo/fixtures/scenario-a-inflated.pdf");
  await expect(page.getByRole("status")).toContainText(
    "Review extracted fields",
  );
  await page
    .getByRole("button", { name: "Source preview", exact: true })
    .click();
  await expect(page.getByRole("img", { name: /Raster preview/ })).toBeVisible();
  await page.screenshot({
    path: path.join(evidenceDir, "07-mobile-documents.png"),
    fullPage: true,
  });
});

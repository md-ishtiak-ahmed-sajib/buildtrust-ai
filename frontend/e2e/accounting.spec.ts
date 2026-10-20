import { test, expect, type Page } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
const creds = JSON.parse(
  fs.readFileSync(process.env.BUILDTRUST_E2E_CREDENTIALS!, "utf8"),
);
async function login(page: Page, role: string) {
  await page.goto("/");
  await page.getByLabel("Email address").fill(`${role}@buildtrust.demo`);
  await page
    .getByLabel("Password", { exact: true })
    .fill(creds[`${role}@buildtrust.demo`]);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await expect(page.getByLabel("Select project")).toBeVisible();
}
async function open(page: Page) {
  await page
    .getByRole("link", { name: "Cost Control & Accounting", exact: true })
    .click();
}
async function changeRole(page: Page, role: string) {
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, role);
  await open(page);
}
async function finish(page: Page, name: string) {
  let card = page
    .locator(".control-card")
    .filter({ has: page.getByRole("heading", { name, exact: true }) });
  await card
    .getByRole("button", { name: "Submit for checking", exact: true })
    .click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(card).toContainText("Submitted");
  await changeRole(page, "manager");
  card = page
    .locator(".control-card")
    .filter({ has: page.getByRole("heading", { name, exact: true }) });
  await card
    .getByRole("button", { name: "Check control", exact: true })
    .click();
  await expect(card).toContainText("Checked");
  await changeRole(page, "admin");
  card = page
    .locator(".control-card")
    .filter({ has: page.getByRole("heading", { name, exact: true }) });
  await card
    .getByRole("button", { name: "Approve control", exact: true })
    .click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(card).toContainText("Approved");
}
test("accounting controls, independent review, revenue margin and accessible forecast", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await login(page, "operator");
  await open(page);
  await page
    .getByRole("button", { name: "Prepare control", exact: true })
    .click();
  let form = page.getByRole("dialog", {
    name: "Prepare independently reviewed control",
  });
  await form
    .getByLabel("Control name", { exact: true })
    .fill("Browser zero-tax policy");
  await form
    .getByLabel("Source evidence and assumptions")
    .fill(
      "Fictional browser policy: explicit zero tax and retention for acceptance example",
    );
  await form.getByRole("button", { name: "Save control draft" }).click();
  await expect(form).toHaveCount(0);
  await finish(page, "Browser zero-tax policy");
  await changeRole(page, "operator");
  await page
    .getByRole("button", { name: "Prepare control", exact: true })
    .click();
  form = page.getByRole("dialog", {
    name: "Prepare independently reviewed control",
  });
  await form.getByLabel("Control type").selectOption("CUSTOMER_CERTIFICATE");
  await form
    .getByLabel("Control name", { exact: true })
    .fill("Browser certified revenue");
  await form
    .getByLabel("Approved accounting policy")
    .selectOption({ label: "Browser zero-tax policy" });
  await form
    .getByLabel("Customer", { exact: true })
    .fill("Fictional browser customer");
  await form.getByLabel("Certificate number").fill("BROWSER-CERT-001");
  await form.getByLabel("Certified revenue").fill("200000");
  await form
    .getByLabel("Source evidence and assumptions")
    .fill(
      "Fictional customer certificate, independently specified revenue 200000 BDT",
    );
  await form.getByRole("button", { name: "Save control draft" }).click();
  await expect(form).toHaveCount(0);
  await finish(page, "Browser certified revenue");
  await changeRole(page, "operator");
  await page
    .getByRole("button", { name: "Prepare control", exact: true })
    .click();
  form = page.getByRole("dialog", {
    name: "Prepare independently reviewed control",
  });
  await form.getByLabel("Control type").selectOption("OPENING_BALANCE");
  await form
    .getByLabel("Control name", { exact: true })
    .fill("Browser reviewed opening cost");
  await form.getByLabel("Journal debit row 1").fill("150000");
  await form.getByLabel("Journal credit row 2").fill("150000");
  await form
    .getByLabel("Source evidence and assumptions")
    .fill(
      "Fictional reviewed opening project cost and accrued liability; no fabricated historical dates",
    );
  await form.getByRole("button", { name: "Save control draft" }).click();
  await expect(form).toHaveCount(0);
  await finish(page, "Browser reviewed opening cost");
  const output = process.env.BUILDTRUST_E2E_OUTPUT!;
  fs.mkdirSync(output, { recursive: true });
  await page.screenshot({
    path: path.join(output, "accounting-controls.png"),
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Performance & Scenarios", exact: true })
    .click();
  await expect(page.getByText("25.000000", { exact: true })).toBeVisible();
  await page
    .getByText("View daily cash flow as a table", { exact: true })
    .click();
  await expect(page.getByRole("table")).toBeVisible();
  await page.getByRole("button", { name: "Explain recorded evidence" }).click();
  await expect(page.locator(".copilot-answer")).toContainText("25.000000");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: path.join(output, "performance-mobile.png"),
    fullPage: false,
    animations: "disabled",
  });
  expect(errors).toEqual([]);
});

import { test, expect, type Page } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
const creds = JSON.parse(
  fs.readFileSync(
    path.resolve(
      process.env.BUILDTRUST_E2E_CREDENTIALS || "../data/demo-credentials.json",
    ),
    "utf8",
  ),
);
const out = process.env.BUILDTRUST_E2E_OUTPUT || "../data/e2e-upgrade";
fs.mkdirSync(out, { recursive: true });
async function login(page: Page, role: string) {
  await page.getByLabel("Email address").fill(`${role}@buildtrust.demo`);
  await page
    .getByLabel("Password", { exact: true })
    .fill(creds[`${role}@buildtrust.demo`]);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await expect(page.getByLabel("Select project")).toBeVisible();
}
async function openUpgrade(page: Page, projectId: number) {
  await page.getByLabel("Select project").selectOption(String(projectId));
  await page
    .getByRole("link", { name: "BOQ & Estimates", exact: true })
    .click();
}

test("BOQ price comparison, forecast, independent checking and approval", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const auth = await request.post("/api/v1/auth/login", {
    data: {
      email: "admin@buildtrust.demo",
      password: creds["admin@buildtrust.demo"],
    },
  });
  const token = (await auth.json()).access_token;
  const created = await request.post("/api/v1/advanced/demo-project", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(created.status()).toBe(201);
  const data = await created.json();
  await page.goto("/");
  await login(page, "operator");
  await openUpgrade(page, data.project_id);
  await expect(page.locator(".estimate-total strong")).toHaveText(
    "1,400,000.00",
  );
  await page.locator(".boq-material-links").getByRole("button").click();
  const dialog = page.getByRole("dialog", {
    name: "Material price comparison",
  });
  await expect(
    dialog.getByText("No currently verifiable online prices", { exact: false }),
  ).toBeVisible();
  await dialog.getByLabel("Source mode").selectOption("DEMO");
  await dialog
    .getByRole("button", { name: "Search prices", exact: true })
    .click();
  await expect(dialog.locator(".quote-card")).toHaveCount(3);
  const wrong = dialog
    .locator(".quote-card")
    .filter({ hasText: "INCOMPATIBLE-DEMO-GRADE" });
  // Specification details are collapsed; the displayed incompatibility still blocks selection.
  await expect(
    dialog
      .locator(".quote-card")
      .filter({ hasText: "Different specification" })
      .getByRole("button", { name: "Use this price" }),
  ).toBeDisabled();
  await page.screenshot({
    path: path.join(out, "upgrade-price-comparison.png"),
    fullPage: true,
  });
  await dialog.locator('.quote-card.recommended').screenshot({path:path.join(out,'upgrade-recommended-offer.png')});
  await dialog
    .locator(".quote-card.recommended")
    .getByRole("button", { name: "Use this price" })
    .click();
  const confirmation = dialog.getByRole("region", {
    name: "Confirm selected rate",
  });
  await expect(
    confirmation.getByText("1480000.00", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    confirmation.getByText("-80000.00", { exact: true }),
  ).toBeVisible();
  await confirmation
    .getByRole("button", { name: "Confirm and recalculate" })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(page.locator(".estimate-total strong")).toHaveText(
    "1,480,000.00",
  );
  await expect(page.getByText("520,000.00", { exact: true }).first()).toBeVisible();
  await page
    .getByRole("button", { name: "Analyze estimate", exact: true })
    .click();
  await expect(page.locator(".copilot-answer")).toContainText("1480000.00");
  await page
    .getByRole("button", { name: "Submit for checking", exact: true })
    .click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.locator(".approval-bar")).toContainText("Submitted");
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "manager");
  await openUpgrade(page, data.project_id);
  await page
    .getByRole("button", { name: "Check estimate", exact: true })
    .click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.locator(".approval-bar")).toContainText("Checked");
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "admin");
  await openUpgrade(page, data.project_id);
  await page
    .getByRole("button", { name: "Approve estimate baseline", exact: true })
    .click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.locator(".approval-bar")).toContainText("Approved");
  await page.screenshot({
    path: path.join(out, "upgrade-approved-estimate.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Create revision", exact: true })
    .click();
  await expect(page.locator(".estimate-heading")).toContainText("Revision 2");
  expect(errors).toEqual([]);
});

test("mobile quantity takeoff calculates and saves actual geometry", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await login(page, "operator");
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page
    .getByRole("link", { name: "Quantity Takeoff", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Calculate quantity", exact: true })
    .click();
  await expect(page.locator(".takeoff-answer")).toContainText("9.600000");
  await page
    .getByRole("button", { name: "Save measurement sheet", exact: true })
    .click();
  await expect(
    page.getByText("Measurement saved for independent checking"),
  ).toBeVisible();
  await expect(page.locator("tbody")).toContainText("9.600000");
  await page.screenshot({
    path: path.join(out, "upgrade-mobile-takeoff.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

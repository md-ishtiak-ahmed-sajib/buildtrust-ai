import { test, expect, type Page } from "./fixtures";
import fs from "node:fs";
import path from "node:path";

const credentials = JSON.parse(fs.readFileSync(process.env.BUILDTRUST_E2E_CREDENTIALS!, "utf8"));
async function login(page: Page, role: string) {
  await page.goto("/");
  await page.getByLabel("Email address").fill(`${role}@buildtrust.demo`);
  await page.getByLabel("Password", { exact: true }).fill(credentials[`${role}@buildtrust.demo`]);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await expect(page.getByLabel("Select project")).toBeVisible();
  await page.getByRole("link", { name: "Commercial Management", exact: true }).click();
}
async function role(page: Page, name: string) {
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, name);
}
async function finish(page: Page, name: string) {
  const card = () => page.locator(".control-card").filter({ has: page.getByRole("heading", { name, exact: true }) });
  await card().getByRole("button", { name: "Submit for checking", exact: true }).click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(card()).toContainText("Submitted");
  await expect(card().getByRole("button", { name: "Check control", exact: true })).toBeDisabled();
  await role(page, "manager");
  await card().getByRole("button", { name: "Check control", exact: true }).click();
  await expect(card()).toContainText("Checked");
  await role(page, "admin");
  await card().getByRole("button", { name: "Approve control", exact: true }).click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(card()).toContainText("Approved");
}

test("commercial contract and cumulative certificate use independent browser approval", async ({ page, request }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const tokens: Record<string, string> = {};
  for (const person of ["operator", "manager", "admin"]) {
    const response = await request.post("/api/v1/auth/login", { data: { email: `${person}@buildtrust.demo`, password: credentials[`${person}@buildtrust.demo`] } });
    tokens[person] = (await response.json()).access_token;
  }
  const headers = (person: string) => ({ Authorization: `Bearer ${tokens[person]}` });
  const project = (await (await request.get("/api/v1/projects", { headers: headers("operator") })).json())[0].id;
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Dhaka" }).format(new Date());
  let response = await request.post("/api/v1/controls", { headers: headers("operator"), data: { project_id: project, name: "Commercial browser policy", payload: { kind: "ACCOUNTING_POLICY", effective_date: today, evidence: "Fictional explicit zero-tax commercial policy" } } });
  expect(response.status()).toBe(201);
  let policy = await response.json();
  for (const [action, person] of [["submit", "operator"], ["check", "manager"], ["approve", "admin"]]) {
    response = await request.post(`/api/v1/controls/${policy.id}/${action}`, { headers: headers(person), data: { expected_version: policy.version } });
    expect(response.status()).toBe(200);
    policy = await response.json();
  }
  response = await request.post("/api/v1/accounting/cost-codes", { headers: headers("operator"), data: { project_id: project, code: "BROWSER.CONCRETE", name: "Browser measured concrete" } });
  expect(response.status()).toBe(201);
  const costCode = await response.json();
  const before = await (await request.get(`/api/v1/accounting/summary?project_id=${project}`, { headers: headers("operator") })).json();
  await login(page, "operator");
  await page.getByRole("button", { name: "Prepare control", exact: true }).click();
  let form = page.getByRole("dialog", { name: "Prepare independently reviewed control" });
  await form.getByLabel("Control name", { exact: true }).fill("Browser construction contract");
  await form.getByLabel("Contract number", { exact: true }).fill("BROWSER-CONTRACT-01");
  await form.getByLabel("Contract direction").selectOption("CUSTOMER");
  await form.getByLabel("Customer (customer contracts)").fill("Fictional commercial client");
  await form.getByLabel("Approved accounting policy").selectOption(String(policy.id));
  await form.getByLabel("Retention percent", { exact: true }).fill("5");
  for (const [key, value] of Object.entries({ code: "CONCRETE", description: "Measured concrete work", quantity: "100", unit: "m3", rate: "1000" })) {
    await form.getByLabel(`${key} row 1`, { exact: true }).fill(value);
  }
  await form.getByLabel("cost code id · row 1").selectOption(String(costCode.id));
  await form.getByLabel("Source evidence and assumptions").fill("Fictional independently approved customer scope and payment terms");
  await form.getByRole("button", { name: "Save control draft" }).click();
  await expect(form).toHaveCount(0);
  await finish(page, "Browser construction contract");
  const controls = await (await request.get(`/api/v1/controls?project_id=${project}`, { headers: headers("operator") })).json();
  const contract = controls.find((row: { name: string }) => row.name === "Browser construction contract");
  await role(page, "operator");
  await page.getByRole("button", { name: "Prepare control", exact: true }).click();
  form = page.getByRole("dialog", { name: "Prepare independently reviewed control" });
  await form.getByLabel("Control type").selectOption("INTERIM_CERTIFICATE");
  await form.getByLabel("Control name", { exact: true }).fill("Browser cumulative certificate");
  await form.getByLabel("Approved contract", { exact: true }).selectOption(String(contract.id));
  await form.getByLabel("Certificate number", { exact: true }).fill("BROWSER-IPC-01");
  await form.getByLabel("item_code row 1", { exact: true }).fill("CONCRETE");
  await form.getByLabel("cumulative_quantity row 1", { exact: true }).fill("50");
  await form.getByLabel("Source evidence and assumptions").fill("Fictional checked cumulative concrete quantity 50 m3 at contractual rate");
  await form.getByRole("button", { name: "Save control draft" }).click();
  await expect(form).toHaveCount(0);
  await finish(page, "Browser cumulative certificate");
  const card = page.locator(".control-card").filter({ has: page.getByRole("heading", { name: "Browser cumulative certificate", exact: true }) });
  await card.getByText("Evidence and calculations", { exact: true }).click();
  await expect(card).toContainText("47500.00");
  const after = await (await request.get(`/api/v1/accounting/summary?project_id=${project}`, { headers: headers("operator") })).json();
  expect(Number(after.recognized_revenue) - Number(before.recognized_revenue || 0)).toBe(50000);
  expect(after.recorded_cash).toBe(before.recorded_cash);
  await page.screenshot({ path: path.join(process.env.BUILDTRUST_E2E_OUTPUT!, "commercial-certificate.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
  expect(errors).toEqual([]);
});

test("Admin creates a local reviewer and assigns project access through the UI", async ({ page, request }) => {
  await login(page, "admin");
  await page.getByRole("link", { name: "Team & Access", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Team & Access", exact: true })).toBeVisible();
  await page.getByLabel("Team member name", { exact: true }).fill("Browser independent reviewer");
  await page.getByLabel("Account email", { exact: true }).fill("browser-reviewer@example.test");
  await page.getByLabel("Initial private password", { exact: true }).fill("Isolated-Browser-Reviewer-2026");
  await page.getByLabel("New account role", { exact: true }).selectOption("AUDITOR");
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  const row = page.getByRole("row").filter({ hasText: "browser-reviewer@example.test" });
  await expect(row).toContainText("No access");
  await row.getByRole("button", { name: "Assign access", exact: true }).click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(row).toContainText("Assigned");
  await page.screenshot({ path: path.join(process.env.BUILDTRUST_E2E_OUTPUT!, "team-project-access.png"), fullPage: true });
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.getByLabel("Email address").fill("browser-reviewer@example.test");
  await page.getByLabel("Password", { exact: true }).fill("Isolated-Browser-Reviewer-2026");
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await expect(page.getByLabel("Select project")).toBeVisible();
  await page.getByRole("link", { name: "Commercial Management", exact: true }).click();
  await expect(page.getByRole("button", { name: "Prepare control", exact: true })).toHaveCount(0);
});

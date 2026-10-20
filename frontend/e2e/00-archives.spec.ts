import { test, expect } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
const credentials = JSON.parse(fs.readFileSync(process.env.BUILDTRUST_E2E_CREDENTIALS!, "utf8"));

test("archived runs retain evidence and are read only; register filters survive navigation", async ({ page, request }) => {
  // The runner supplies a private test database. Reset never targets the user's app.
  const login = await request.post("/api/v1/auth/login", { data: {
    email: "admin@buildtrust.demo", password: credentials["admin@buildtrust.demo"] } });
  const headers = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const projects = await (await request.get("/api/v1/projects", { headers })).json();
  const original = projects[0];
  const before = await (await request.get(`/api/v1/documents?project_id=${original.id}`, { headers })).json();
  expect((await request.post("/api/v1/demo/reset", { headers })).ok()).toBeTruthy();
  await page.goto("/");
  await page.getByLabel("Email address").fill("auditor@buildtrust.demo");
  await page.getByLabel("Password", { exact: true }).fill(credentials["auditor@buildtrust.demo"]);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await page.getByLabel("Select project").selectOption(String(original.id));
  await expect(page.getByText("Archived run · read only.", { exact: false })).toBeVisible();
  await page.getByRole("link", { name: "Review Inbox", exact: true }).click();
  await page.getByLabel("Search register").fill("CEMENT");
  await expect(page.getByLabel("Search register")).toHaveValue("CEMENT");
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await page.getByRole("link", { name: "Review Inbox", exact: true }).click();
  await expect(page.getByLabel("Search register")).toHaveValue("CEMENT");
  const archived = await (await request.get(`/api/v1/documents?project_id=${original.id}`, { headers })).json();
  expect(archived).toEqual(before);
  const denied = await request.post("/api/v1/estimates", { headers, data: {
    project_id: original.id, name: "Archive must reject writes", import_boq: false } });
  expect(denied.status()).toBe(409);
  const output = process.env.BUILDTRUST_E2E_OUTPUT!;
  fs.mkdirSync(output, { recursive: true });
  await page.screenshot({ path: path.join(output, "archived-register.png"), fullPage: true });
});

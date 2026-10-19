import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
const creds = JSON.parse(
  fs.readFileSync(process.env.BUILDTRUST_E2E_CREDENTIALS!, "utf8"),
);
async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("Email address").fill("operator@buildtrust.demo");
  await page
    .getByLabel("Password", { exact: true })
    .fill(creds["operator@buildtrust.demo"]);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await expect(page.getByLabel("Select project")).toBeVisible();
}

test('failed register loading retries without leaving the current workspace', async ({page}) => {
  await login(page);
  let unavailable=true;
  await page.route('**/api/v1/registers/documents?**', async route => {
    if (unavailable) await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:{code:'TEMPORARILY_UNAVAILABLE',message:'Temporary isolated register failure'}})});
    else await route.continue();
  });
  await page.getByRole('link',{name:'Review Inbox',exact:true}).click();
  await page.getByLabel('Register',{exact:true}).selectOption('documents');
  await expect(page.getByRole('alert')).toContainText('Temporary isolated register failure');
  unavailable=false;
  await page.getByRole('button',{name:'Retry loading',exact:true}).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.getByText(/matching records/)).toBeVisible();
});

test("takeoff inputs invalidate old results and recalculate", async ({
  page,
}) => {
  await login(page);
  await page
    .getByRole("link", { name: "Quantity Takeoff", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Calculate quantity", exact: true })
    .click();
  await expect(page.locator(".takeoff-answer")).toContainText("9.600000");
  await page.getByLabel(/^length$/i).fill("0.8");
  await expect(page.locator(".takeoff-answer")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Calculate quantity", exact: true })
    .click();
  await expect(page.locator(".takeoff-answer")).toContainText("19.200000");
});

test("unsaved estimate Save Discard Stay and printable BOQ content", async ({
  page,
  request,
}) => {
  const auth = await request.post("/api/v1/auth/login", {
    data: {
      email: "operator@buildtrust.demo",
      password: creds["operator@buildtrust.demo"],
    },
  });
  const headers = {
    Authorization: `Bearer ${(await auth.json()).access_token}`,
  };
  const projects = await (
    await request.get("/api/v1/projects", { headers })
  ).json();
  const other = await (
    await request.post("/api/v1/estimates", {
      headers,
      data: {
        project_id: projects[0].id,
        name: "Another guard version",
        import_boq: true,
      },
    })
  ).json();
  const created = await request.post("/api/v1/estimates", {
    headers,
    data: {
      project_id: projects[0].id,
      name: "Print and draft guard",
      import_boq: true,
    },
  });
  expect(created.status()).toBe(201);
  const original = await created.json();
  await login(page);
  await page
    .getByRole("link", { name: "BOQ & Estimates", exact: true })
    .click();
  await page
    .getByLabel("Select estimate version")
    .selectOption(String(original.id));
  const name = page.getByLabel("Estimate name", { exact: true });
  await name.fill("Kept through navigation");
  await page
    .getByRole("link", { name: "Quantity Takeoff", exact: true })
    .click();
  let dialog = page.getByRole("dialog", { name: "Unsaved estimate changes" });
  await dialog.getByRole("button", { name: "Stay", exact: true }).click();
  await expect(name).toHaveValue("Kept through navigation");
  await page
    .getByRole("link", { name: "Quantity Takeoff", exact: true })
    .click();
  await dialog
    .getByRole("button", { name: "Save and continue", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Quantity Takeoff", exact: true }),
  ).toBeVisible();
  await page.goBack();
  await expect(name).toHaveValue("Kept through navigation");
  await name.fill("Preserve after failed save");
  await page.route(`**/api/v1/estimates/${original.id}`, (route) =>
    route.request().method() === "PATCH"
      ? route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({
            error: {
              code: "TEST_SAVE_FAILURE",
              message: "Save temporarily unavailable",
            },
          }),
        })
      : route.continue(),
  );
  await page
    .getByRole("link", { name: "Quantity Takeoff", exact: true })
    .click();
  await dialog
    .getByRole("button", { name: "Save and continue", exact: true })
    .click();
  await expect(dialog.getByRole("alert")).toContainText(
    "Save temporarily unavailable",
  );
  await dialog.getByRole("button", { name: "Stay", exact: true }).click();
  await expect(name).toHaveValue("Preserve after failed save");
  await page.unroute(`**/api/v1/estimates/${original.id}`);
  await page
    .getByLabel("Select estimate version")
    .selectOption(String(other.id));
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Stay", exact: true }).click();
  await expect(name).toHaveValue("Preserve after failed save");
  if (projects.length > 1) {
    await page
      .getByLabel("Select project")
      .selectOption(String(projects[1].id));
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "Stay", exact: true }).click();
    await expect(name).toHaveValue("Preserve after failed save");
  }
  await name.fill("Discard this");
  await page
    .getByRole("link", { name: "Quantity Takeoff", exact: true })
    .click();
  await dialog.getByRole("button", { name: "Discard", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Quantity Takeoff", exact: true }),
  ).toBeVisible();
  await page.goBack();
  await expect(name).toHaveValue("Kept through navigation");
  await page.emulateMedia({ media: "print" });
  const pdf = await page.pdf({ format: "A4", printBackground: true });
  const text = execFileSync(
    "uv",
    [
      "run",
      "--project",
      "../backend",
      "python",
      "-c",
      "import sys,pymupdf; sys.stdout.reconfigure(encoding='utf-8'); d=pymupdf.open(stream=sys.stdin.buffer.read(),filetype='pdf'); print(''.join(p.get_text() for p in d))",
    ],
    { input: pdf, encoding: "utf8" },
  );
  expect(text).toContain(original.fields.lines[0].code);
  expect(text.replaceAll(",", "")).toContain(original.total);
  const output = process.env.BUILDTRUST_E2E_OUTPUT!;
  fs.mkdirSync(output, { recursive: true });
  fs.writeFileSync(path.join(output, "estimate-print.pdf"), pdf);
  await page.screenshot({
    path: path.join(output, "estimate-print.png"),
    fullPage: true,
  });
});

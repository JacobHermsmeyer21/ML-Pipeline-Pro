import { expect, test } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { mockApi } from "./fixtures/api";

const exampleCsv = fileURLToPath(new URL("../public/example.csv", import.meta.url));

test.beforeEach(async ({ page }) => {
  page.on("pageerror", (error) => { throw error; });
});

async function open(page: import("@playwright/test").Page) {
  await page.goto("/dashboard/");
  await expect(page.locator("#service-status")).toContainText("Workspace connected");
}

test("connects with project and key", async ({ page }) => {
  const log = await mockApi(page);
  await open(page);
  await page.locator("#connection-open").click();
  await page.locator("#connection-project").fill("alpha");
  await page.locator("#connection-key").fill("secret-key");
  const before = log.requests.length;
  await page.locator("#connection-form button[type=submit]").click();
  await expect.poll(() => log.requests.length).toBeGreaterThan(before + 3);
  for (const request of log.requests.slice(before)) {
    expect(request.headers["x-project-id"]).toBe("alpha");
    expect(request.headers["x-api-key"]).toBe("secret-key");
  }
});

test("review-then-train submits once", async ({ page }) => {
  const log = await mockApi(page);
  await open(page);
  await page.locator("#train-submit").click();
  await expect(page.locator("#review-dialog")).toBeVisible();
  await page.locator("#review-confirm").dblclick();
  await expect(page.locator("#run-detail")).toBeVisible();
  expect(log.count("POST", /^\/experiments$/)).toBe(1);
  const post = log.requests.find((item) => item.method === "POST" && item.path === "/experiments")!;
  expect(post.headers["idempotency-key"]).toMatch(/^[0-9a-f-]{36}$/);
});

test("pending training survives reload", async ({ page }) => {
  await mockApi(page, { failExperimentPost: 503 });
  await open(page);
  await page.locator("#train-submit").click();
  await page.locator("#review-confirm").click();
  await expect(page.locator("#training-recovery")).toBeVisible();
  await page.reload();
  await expect(page.locator("#training-recovery")).toBeVisible();
  await expect(page.locator("#train-submit")).toBeDisabled();
});

test("upload preview then prepare", async ({ page }) => {
  const log = await mockApi(page);
  await open(page);
  await page.locator('[data-view="datasets"]').click();
  await page.locator("#dataset-file").setInputFiles(exampleCsv);
  await expect(page.locator("#dataset-target")).toHaveValue("target");
  await page.locator("#upload-submit").click();
  await expect(page.locator("#encoding-review")).toBeVisible();
  await page.locator("#prepare-save").click();
  await expect(page.locator("#upload-result")).toContainText("Dataset verified and saved");
  expect(log.count("POST", /^\/datasets\/preview$/)).toBe(1);
  expect(log.count("POST", /^\/datasets\/prepare$/)).toBe(1);
});

test("column edit saves new version", async ({ page }) => {
  const log = await mockApi(page);
  await open(page);
  await page.locator('[data-view="datasets"]').click();
  await page.getByRole("button", { name: "Edit columns" }).click();
  await expect(page.locator("#column-dialog")).toBeVisible();
  await page.locator("#column-version").fill("v2");
  await page.getByLabel("Keep feature_2").uncheck();
  await page.locator("#column-form button[type=submit]").click();
  await expect(page.locator("#column-save")).toBeEnabled();
  await page.locator("#column-save").click();
  await page.locator("#review-confirm").click();
  await expect(page.locator("#global-message")).toContainText("Original versions and training runs are preserved");
  expect(log.count("POST", /^\/datasets\/[^/]+\/columns$/)).toBe(1);
});

test("model delete shows scope first", async ({ page }) => {
  const log = await mockApi(page);
  await open(page);
  await page.locator("#models-manage-open").click();
  await page.getByRole("button", { name: "Delete model" }).click();
  await expect(page.locator("#review-dialog")).toBeVisible();
  expect(log.count("DELETE", /^\/models\//)).toBe(0);
  await page.locator("#review-confirm").click();
  await expect(page.locator("#global-message")).toContainText("Permanently deleted");
  const preview = log.requests.findIndex((item) => item.path.endsWith("/deletion-preview"));
  const removal = log.requests.findIndex((item) => item.method === "DELETE");
  expect(preview).toBeGreaterThanOrEqual(0);
  expect(removal).toBeGreaterThan(preview);
  expect(log.count("DELETE", /^\/models\//)).toBe(1);
});

for (const decision of ["reject", "approve"] as const) {
  test(`chat ${decision} sends exactly one decision`, async ({ page }) => {
    const log = await mockApi(page);
    await open(page);
    await page.locator("#chat-input").fill("Train my dataset");
    await page.locator("#chat-send").click();
    const button = page.getByRole("button", { name: decision === "approve" ? "Approve action" : "Reject" });
    await expect(button).toBeEnabled();
    await button.click();
    await expect(page.locator("#global-message")).toContainText("Saved action");
    const decisions = log.requests.filter((item) => item.method === "POST" && item.path.endsWith("/decision"));
    expect(decisions).toHaveLength(1);
    expect(JSON.parse(decisions[0].body!).decision).toBe(decision);
    expect(log.count("POST", /^\/experiments$/)).toBe(0);
  });
}

test("monitoring empty state", async ({ page }) => {
  await mockApi(page);
  await open(page);
  await page.locator('[data-view="monitoring"]').click();
  await expect(page.locator("#monitor-summary")).toContainText("Select a registered version");
});

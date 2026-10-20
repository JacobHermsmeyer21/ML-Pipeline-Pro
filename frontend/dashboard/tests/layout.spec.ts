import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { dataset, experiment, mockApi, model } from "./fixtures/api";

const widths = [360, 390, 768, 1024, 1440];
const banned = ["Your next model starts here", "Let's build something useful", "Built to experiment", "BUILD YOUR PIPELINE", "Your thinking partner"];
const longName = "a".repeat(80);

async function open(page: Page) {
  await page.goto("/dashboard/");
  await expect(page.locator("#service-status")).toContainText("Workspace connected");
}
const noPageOverflow = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

for (const width of widths) {
  test(`no horizontal page scroll at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockApi(page, { datasets: [dataset({ name: longName })], models: [model({ name: longName })] });
    await open(page);
    expect(await noPageOverflow(page)).toBe(true);
    for (const view of ["datasets", "monitoring"]) {
      if (width < 900) await page.locator("#nav-toggle").click();
      await page.locator(`[data-view="${view}"]`).click();
      expect(await noPageOverflow(page), view).toBe(true);
    }
    await page.locator('[data-view="runs"]').first().evaluate((node: HTMLElement) => node.click());
    await page.waitForTimeout(300); // let the drawer finish closing before the capture
    await page.screenshot({ path: `test-results/screens/${width}.png`, fullPage: true });
  });
}

test("100 experiments scroll inside the table at 360px", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  const runs = Array.from({ length: 100 }, (_, index) => experiment(`ex_${String(index).padStart(12, "0")}`, "succeeded"));
  await mockApi(page, { experiments: runs });
  await open(page);
  await expect(page.locator("#runs-body tr")).toHaveCount(100);
  expect(await noPageOverflow(page)).toBe(true);
});

test("column dialog with 40 columns keeps save reachable at 390x700", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 700 });
  await mockApi(page);
  const columns = Array.from({ length: 40 }, (_, index) => ({ name: `feature_${index}`, output_columns: [`feature_${index}`] }));
  await page.route("**/api/v1/datasets/ds_1/columns", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({
    dataset_id: "ds_1", name: "customer_outcomes", version: "v1", source_sha256: "b".repeat(64), columns,
    target_column: "target", split_column: "split", row_counts: { train: 80, validation: 20, test: 20 }, encoded_width: 40 }) }));
  await open(page);
  await page.locator("#nav-toggle").click();
  await page.locator('[data-view="datasets"]').click();
  await page.getByRole("button", { name: "Edit columns" }).click();
  const box = await page.locator("#column-dialog").boundingBox();
  expect(box!.height).toBeLessThanOrEqual(700);
  await page.locator("#column-save").scrollIntoViewIfNeeded();
  await expect(page.locator("#column-save")).toBeInViewport();
});

test("mobile nav drawer works from the keyboard", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 });
  await mockApi(page);
  await open(page);
  const toggle = page.locator("#nav-toggle");
  await expect(page.locator(".sidebar")).not.toBeInViewport();
  await toggle.focus();
  await page.keyboard.press("Enter");
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator(".sidebar")).toBeInViewport();
  await page.keyboard.press("Escape");
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(toggle).toBeFocused();
});

test("long error notice wraps inside its box at 360px", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await mockApi(page);
  await page.route("**/api/v1/tuning-jobs**", (route) => route.fulfill({ status: 503, contentType: "application/json",
    body: JSON.stringify({ error: { code: "storage_unavailable", message: "Metadata storage is unavailable", correlation_id: "51e922bb-b285-4d11-b5fb-241db04be355" } }) }));
  await page.goto("/dashboard/");
  const notice = page.locator("#global-message");
  await expect(notice).toBeVisible();
  expect(await notice.evaluate((node) => node.scrollWidth <= node.clientWidth)).toBe(true);
  expect(await noPageOverflow(page)).toBe(true);
});

test("plain product copy and no sparkle motif", async ({ page }) => {
  await mockApi(page);
  await open(page);
  const text = await page.locator("body").innerText();
  for (const phrase of banned) expect(text).not.toContain(phrase);
  await expect(page.locator('use[href="#i-spark"]')).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Pipeline agent" })).toBeVisible();
});

test("no serious accessibility violations", async ({ page }) => {
  await mockApi(page);
  await open(page);
  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter((item) => item.impact === "serious" || item.impact === "critical");
  expect(serious.flatMap((item) => item.nodes.map((node) => `${item.id}: ${node.target.join(" ")} ${node.any[0]?.message ?? ""}`))).toEqual([]);
});

test("closed dialogs and drawer controls stay hidden on desktop", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await mockApi(page);
  await open(page);
  for (const id of ["connection-dialog", "model-dialog", "models-dialog", "review-dialog", "column-dialog"]) {
    await expect(page.locator(`#${id}`), id).toBeHidden();
  }
  await expect(page.locator("#nav-toggle")).toBeHidden();
  await expect(page.locator("#nav-close")).toBeHidden();
  await expect(page.locator(".sidebar")).toBeInViewport();
});

test("truncated names expose their full text as a title", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 900 });
  await mockApi(page, { datasets: [dataset({ name: longName })], models: [model({ name: longName })] });
  await open(page);
  const cell = page.locator("#runs-body tr").first();
  await expect(cell.locator("td strong")).toHaveAttribute("title", longName);
  await expect(cell.locator("td small")).toHaveAttribute("title", new RegExp(`^${longName} · v1`));
  await expect(page.locator("#chat-context")).toHaveAttribute("title", `${longName} / ${longName}`);
  await expect(page.locator("#project-label")).toHaveAttribute("title", "demo");
});

test("drawer keeps keyboard focus inside and lands on the workspace after a choice", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 });
  await mockApi(page);
  await open(page);
  await page.locator("#nav-toggle").click();
  await expect(page.locator(".page")).toHaveAttribute("inert", "");
  await page.locator('[data-view="datasets"]').focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(".page")).not.toHaveAttribute("inert", "");
  await expect(page.locator("#workspace")).toBeFocused();
});

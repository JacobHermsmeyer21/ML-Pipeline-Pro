import { expect, test, type Page } from "@playwright/test";
import { experiment, experimentRunning, mockApi } from "./fixtures/api";

const configs = [[0.001, 8, 0.71], [0.003, 16, 0.84], [0.01, 16, 0.912], [0.03, 64, 0.88], [0.1, 128, 0.62], [0.01, 256, 0.95]] as const;
const runs = configs.map(([learning_rate, hidden_units, f1], index) => experiment(`ex_scene_${index}0000`, "succeeded", {
  config: { epochs: 30, batch_size: 16, learning_rate, hidden_units, max_runtime_seconds: 60, seed: 42 },
  metrics: { validation_f1: f1, validation_accuracy: f1, best_epoch: 10 },
}));
const canvas = (page: Page) => page.locator("#scene-canvas");
const pixels = (page: Page) => canvas(page).evaluate((node: HTMLCanvasElement) => node.toDataURL());

async function open(page: Page) {
  await page.goto("/dashboard/");
  await expect(page.locator("#service-status")).toContainText("Workspace connected");
}

test("experiment space plots runs and opens one on click", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mockApi(page, { experiments: [...runs, experimentRunning] });
  await open(page);
  await expect(page.locator("#scene-label")).toHaveText(/^7 experiments plotted, 6 finished\./);
  await expect(page.locator("#scene-empty")).toBeHidden();
  await page.waitForTimeout(1500); // points finish rising
  await page.screenshot({ path: "test-results/screens/scene-1440.png" });
  // Hovering a plotted point names its run; clicking it opens the experiment detail.
  // The scan dispatches hover events in the page so the spinning view cannot outrun it.
  const hit = await canvas(page).evaluate((node: HTMLCanvasElement) => {
    const box = node.getBoundingClientRect(), tip = document.getElementById("scene-tip")!;
    for (let y = box.top + 4; y < box.bottom; y += 4) for (let x = box.left + 4; x < box.right; x += 4) {
      node.dispatchEvent(new PointerEvent("pointermove", { clientX: x, clientY: y, bubbles: true }));
      if (!tip.hidden) return { x, y };
    }
    return null;
  });
  expect(hit).not.toBeNull();
  await expect(page.locator("#scene-tip")).toContainText("baseline_mlp");
  await page.mouse.move(hit!.x, hit!.y);
  await page.mouse.down(); await page.mouse.up();
  await expect(page.locator("#run-detail")).toBeVisible();
});

test("dragging turns the view and keys move it too", async ({ page }) => {
  await mockApi(page, { experiments: runs });
  await open(page);
  const box = (await canvas(page).boundingBox())!;
  await page.waitForTimeout(1200);
  await page.mouse.move(box.x + 20, box.y + box.height - 20); // empty corner: no tooltip, no auto-spin
  await page.waitForTimeout(100);
  const before = await pixels(page);
  await page.mouse.down();
  await page.mouse.move(box.x + 220, box.y + box.height - 40, { steps: 8 });
  await page.mouse.up();
  expect(await pixels(page)).not.toBe(before);
  await canvas(page).focus();
  const turned = await pixels(page);
  await page.keyboard.press("ArrowLeft");
  await expect.poll(() => pixels(page)).not.toBe(turned);
});

test("reduced motion holds the view still", async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: "reduce" });
  const page = await context.newPage();
  await mockApi(page, { experiments: [...runs, experimentRunning] });
  await open(page);
  await page.waitForTimeout(300);
  const first = await pixels(page);
  await page.waitForTimeout(800);
  expect(await pixels(page)).toBe(first);
  await context.close();
});

test("empty workspace explains the space", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await mockApi(page, { experiments: [] });
  await open(page);
  await expect(page.locator("#scene-empty")).toBeVisible();
  await expect(page.locator("#scene-label")).toHaveText("No experiments to plot yet.");
  await page.waitForTimeout(1200);
  await page.screenshot({ path: "test-results/screens/scene-390.png", fullPage: true });
});

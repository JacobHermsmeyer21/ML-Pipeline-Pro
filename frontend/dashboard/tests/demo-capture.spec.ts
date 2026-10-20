import { expect, test, type Page } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { experiment, mockApi } from "./fixtures/api";

// Captures the README walkthrough frames. Run on demand: DEMO_CAPTURE=1 npx playwright test demo-capture
test.skip(!process.env.DEMO_CAPTURE, "Set DEMO_CAPTURE=1 to record README demo frames");

const exampleCsv = fileURLToPath(new URL("../public/example.csv", import.meta.url));
const out = process.env.DEMO_CAPTURE_DIR ?? "test-results/demo";

async function frame(page: Page, index: number, caption: string) {
  await page.evaluate(({ index, caption }) => {
    document.getElementById("demo-caption")?.remove();
    const bar = document.createElement("div");
    bar.id = "demo-caption";
    bar.textContent = `${index}. ${caption}    ·    sample data, mocked API`;
    Object.assign(bar.style, {
      position: "fixed", left: "0", right: "0", bottom: "0", zIndex: "99", padding: "12px 20px",
      background: "rgba(20,32,28,0.92)", color: "#F3F5F4", font: "500 16px 'IBM Plex Sans', sans-serif",
    });
    document.body.append(bar);
  }, { index, caption });
  await page.waitForTimeout(250);
  await page.screenshot({ path: `${out}/frame-${index}.png` });
}

test("record README demo frames", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await mockApi(page, {
    config: { uploads_enabled: true, max_upload_bytes: 10_000_000, max_dataset_rows: 100_000,
      grafana_origin: "http://127.0.0.1:3000", chat_enabled: true, chat_backend: "anthropic", chat_model: "claude-opus-5-5" },
    experiments: [experiment("ex_done_000001", "succeeded"), experiment("ex_done_000002", "succeeded", {
      metrics: { validation_f1: 0.874, validation_accuracy: 0.9, best_epoch: 9 } })],
  });
  await page.goto("/dashboard/");
  await expect(page.locator("#service-status")).toContainText("Workspace connected");
  await frame(page, 1, "Overview: best validation F1, experiments and the Claude agent");

  await page.locator('[data-view="datasets"]').click();
  await page.locator("#dataset-file").setInputFiles(exampleCsv);
  await page.locator("#upload-submit").click();
  await expect(page.locator("#encoding-review")).toBeVisible();
  await page.locator("#encoding-review").scrollIntoViewIfNeeded();
  await frame(page, 2, "Upload a CSV and review how each column is encoded");

  await page.locator('[data-view="runs"]').first().click();
  await page.locator("#train-submit").click();
  await expect(page.locator("#review-dialog")).toBeVisible();
  await frame(page, 3, "Review the training settings before anything runs");

  await page.locator("#review-confirm").click();
  await expect(page.locator("#run-detail")).toBeVisible();
  await page.locator("#run-detail").scrollIntoViewIfNeeded();
  await frame(page, 4, "The run is queued once and its results appear here");

  await page.locator("#chat-input").fill("Train my dataset with the baseline model");
  await page.locator("#chat-send").click();
  await expect(page.getByRole("button", { name: "Approve action" })).toBeEnabled();
  await page.locator(".agent-panel").scrollIntoViewIfNeeded();
  await frame(page, 5, "Claude proposes a training run; nothing starts until you approve");

  await page.locator('[data-view="monitoring"]').click();
  await frame(page, 6, "Monitoring: Grafana graphs per registered model version");
});

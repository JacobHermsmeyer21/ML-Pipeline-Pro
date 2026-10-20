import { expect, test } from "@playwright/test";
import { experiment, mockApi } from "./fixtures/api";

const strip = (page: import("@playwright/test").Page) => page.locator(".depth-card");

test("readout strip tilts toward the pointer", async ({ page }) => {
  await mockApi(page);
  await page.goto("/dashboard/");
  await expect(page.locator("astro-island")).not.toHaveAttribute("ssr", "");
  const box = (await strip(page).boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.9, box.y + box.height * 0.2);
  await expect.poll(() => strip(page).evaluate((node) => getComputedStyle(node).transform)).not.toBe("none");
  await page.mouse.move(5, box.y + box.height + 200);
  await expect.poll(() => strip(page).evaluate((node) => getComputedStyle(node).transform)).toBe("none");
});

test("reduced motion keeps the strip flat", async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: "reduce" });
  const page = await context.newPage();
  await mockApi(page);
  await page.goto("/dashboard/");
  await expect(page.locator("astro-island")).not.toHaveAttribute("ssr", "");
  const box = (await strip(page).boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.9, box.y + box.height * 0.2);
  await page.waitForTimeout(200);
  expect(await strip(page).evaluate((node) => getComputedStyle(node).transform)).toBe("none");
  await context.close();
});

test("hydration keeps behavior-owned values and the CSP stays quiet", async ({ page }) => {
  const messages: string[] = [];
  page.on("console", (message) => messages.push(message.text()));
  const runs = ["ex_a00000000001", "ex_b00000000002", "ex_c00000000003"].map((id) => experiment(id, "succeeded"));
  await mockApi(page, { experiments: runs });
  await page.goto("/dashboard/");
  await expect(page.locator("astro-island")).not.toHaveAttribute("ssr", "");
  await expect(page.locator("#stat-runs")).toHaveText("3");
  await expect(page.locator("#runs-empty")).toBeHidden();
  expect(messages.filter((text) => text.includes("Content Security Policy"))).toEqual([]);
});

import { defineConfig, devices } from "@playwright/test";

// The built page is served by the real FastAPI app so its CSP headers apply;
// every /api/v1 call is answered by tests/fixtures/api.ts.
export default defineConfig({
  testDir: "tests",
  fullyParallel: true,
  reporter: [["list"]],
  use: { baseURL: "http://127.0.0.1:8123", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "uv run --locked uvicorn ml_pipeline_pro.main:create_app --factory --port 8123 --no-access-log",
    cwd: "../..",
    url: "http://127.0.0.1:8123/api/v1/health/live",
    reuseExistingServer: !process.env.CI,
    stdout: "ignore",
    stderr: "pipe",
    env: { MLPP_ENVIRONMENT: "development", MLPP_DEPENDENCY_TIMEOUT_SECONDS: "1" },
  },
});

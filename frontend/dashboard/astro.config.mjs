import { defineConfig } from "astro/config";
import react from "@astrojs/react";

// Built output is committed and served by FastAPI at /dashboard/.
export default defineConfig({
  outDir: "../../src/ml_pipeline_pro/dashboard",
  base: "/dashboard/",
  build: { format: "file", inlineStylesheets: "never", assets: "_astro" },
  vite: {
    build: { assetsInlineLimit: 0 },
    server: { proxy: { "/api": "http://127.0.0.1:8000", "/dashboard/config.json": "http://127.0.0.1:8000" } },
  },
  integrations: [react()],
});

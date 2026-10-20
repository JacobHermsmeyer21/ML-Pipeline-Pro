// Hash every inline <script>/<style> block so FastAPI can allow exactly those in its CSP header.
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";

const root = new URL("../../../src/ml_pipeline_pro/dashboard/", import.meta.url);
const html = readFileSync(new URL("index.html", root), "utf8");
const digest = (body) => `'sha256-${createHash("sha256").update(body, "utf8").digest("base64")}'`;
const inline = (tag) =>
  [...html.matchAll(new RegExp(`<${tag}(?![^>]*\\bsrc=)[^>]*>([\\s\\S]*?)</${tag}>`, "g"))].map((match) => digest(match[1]));
const hashes = { "script-src": [...new Set(inline("script"))], "style-src": [...new Set(inline("style"))] };
writeFileSync(new URL("csp-hashes.json", root), `${JSON.stringify(hashes, null, 2)}\n`);
if (/\sstyle="/.test(html)) throw new Error("Inline style attributes are not allowed by the dashboard CSP.");

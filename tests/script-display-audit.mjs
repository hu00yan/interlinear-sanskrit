import { chromium } from "playwright-core";
import { mkdir, writeFile } from "node:fs/promises";

const base = process.env.SCRIPT_DISPLAY_URL ?? "http://127.0.0.1:4177";
const out = "qa-report/assets/script-display";
await mkdir(out, { recursive: true });
const browser = await chromium.launch({ headless: true });
const report = [];

async function check(route, label, width) {
  const page = await browser.newPage({ viewport: { width, height: 900 } });
  const errors = [];
  page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
  await page.goto(`${base}/#/${route}`, { waitUntil: "networkidle" });
  await page.waitForSelector(".unit-scripts .wcell");
  const control = page.locator(".script-mode-control").first();
  const state = async () => page.evaluate(() => ({
    mode: document.body.dataset.scriptMode,
    iast: [...document.querySelectorAll('[data-generated-script] .iast-line')]
      .filter((node) => getComputedStyle(node).display !== "none").length,
    deva: [...document.querySelectorAll('[data-generated-script] .deva-line')]
      .filter((node) => getComputedStyle(node).display !== "none").length,
    width: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  await control.getByRole("button", { name: "IAST" }).click();
  const iast = await state();
  if (iast.mode !== "iast" || iast.deva !== 0) throw new Error(`${label}: IAST default failed`);
  await control.getByRole("button", { name: "Both" }).click();
  const both = await state();
  if (both.mode !== "both" || !both.iast || !both.deva) throw new Error(`${label}: both failed`);
  await control.getByRole("button", { name: "देवनागरी" }).click();
  const deva = await state();
  if (deva.mode !== "deva" || deva.iast !== 0 || !deva.deva) throw new Error(`${label}: Devanagari-only failed`);
  if (deva.width > deva.client) throw new Error(`${label}: horizontal overflow`);
  await page.reload({ waitUntil: "networkidle" });
  if (await page.locator("body").getAttribute("data-script-mode") !== "deva") throw new Error(`${label}: mode did not persist`);
  await page.screenshot({ path: `${out}/${label}-${width}.png`, fullPage: true });
  report.push({ label, width, iast, both, deva, errors });
  if (errors.length) throw new Error(`${label}: console errors ${errors.join("; ")}`);
  await page.close();
}

try {
  // Bhagavad Gita, Lotus and Dhammapada respectively exercise Sanskrit verse,
  // Sanskrit prose, and Pali's display-only conversion.
  for (const width of [1440, 390]) {
    await check("bhagavadgita", "bhg", width);
    await check("saddharmapundarika", "lotus", width);
    await check("pali/pali-dhammapada", "dhammapada", width);
  }
  await writeFile("qa-report/script-display.md", `# Script Display Audit\n\nVerified ${report.length} reader surfaces at ${base}.\n\n\`\`\`json\n${JSON.stringify(report, null, 2)}\n\`\`\`\n`);
} finally {
  await browser.close();
}

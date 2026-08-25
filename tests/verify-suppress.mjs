import { chromium } from "@playwright/test";
const EXE = "/Users/huyan00/Library/Caches/ms-playwright/chromium-1187/chrome-mac/Chromium.app/Contents/MacOS/Chromium";
const browser = await chromium.launch({ executablePath: EXE });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 950 } })).newPage();
await page.goto("http://localhost:4176/#/gandavyuha", { waitUntil: "domcontentloaded" });
await page.waitForSelector(".unit-scripts .w", { timeout: 20000 });
await page.waitForTimeout(1500);
const r = {};
r.sidebarInlineTlLines = await page.locator(".tl-line").count();
r.sidebarRows = await page.locator(".tr-sidebar .sb-row").count();
// switch to 行间 -> inline zh lines should appear (partial alignment => en fallback lines), sidebar hides
await page.locator(".view-ctl button", { hasText: "行间" }).click();
await page.waitForTimeout(2500);
r.interlineSidebarHidden = await page.evaluate(() => document.querySelector(".tr-sidebar").classList.contains("hidden"));
r.interlineTlLines = await page.locator(".tl-line").count();
// back to 侧栏
await page.locator(".view-ctl button", { hasText: "侧栏" }).click();
await page.waitForTimeout(1500);
r.backToSidebarRows = await page.locator(".tr-sidebar .sb-row").count();
r.inlineClearedAgain = await page.locator(".tl-line").count();
console.log(JSON.stringify(r, null, 1));
await browser.close();

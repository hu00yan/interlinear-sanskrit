import { chromium } from "@playwright/test";
const EXE = "/Users/huyan00/Library/Caches/ms-playwright/chromium-1187/chrome-mac/Chromium.app/Contents/MacOS/Chromium";
const ORIG = process.argv[2] || "नगाधिराजः";
const browser = await chromium.launch({ executablePath: EXE });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 950 } })).newPage();
await page.goto("http://localhost:4176/#/kumarasambhava", { waitUntil: "domcontentloaded" });
await page.waitForSelector(".unit-scripts .w", { timeout: 20000 });
const tok = page.locator(`.unit-scripts .w[data-orig="${ORIG}"]`).first();
if (await tok.count()) {
  await tok.click();
  await page.waitForTimeout(2000);
  const panelTxt = await page.locator(".side-panel").innerText();
  const members = await page.locator(".side-panel .comp-member").allInnerTexts();
  console.log(JSON.stringify({
    token: ORIG,
    hasHeader: /复合词成分/.test(panelTxt),
    greek: /[\u0370-\u03ff]/.test(panelTxt),
    members,
  }, null, 1));
} else {
  console.log(JSON.stringify({ found: false, token: ORIG }));
}
await browser.close();

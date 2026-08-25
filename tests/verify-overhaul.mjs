// Read-only verification of the reader-UX overhaul against :4176.
// Run: node tests/verify-overhaul.mjs
import { chromium } from "@playwright/test";

const BASE = "http://localhost:4176";
const EXE = "/Users/huyan00/Library/Caches/ms-playwright/chromium-1187/chrome-mac/Chromium.app/Contents/MacOS/Chromium";

async function main() {
  const browser = await chromium.launch({ executablePath: EXE });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 950 } });
  const page = await ctx.newPage();
  const out = {};
  const GREEK = /[\u0370-\u03ff\u1f00-\u1fff]/;

  // ---- 1. lookup राम / rāma -> parse cards + MW, no Greek glyphs ----
  await page.goto(BASE + "/", { waitUntil: "domcontentloaded" });
  const wl = page.locator(".word-lookup .wl-input");
  await wl.waitFor({ timeout: 15000 });
  await wl.fill("राम");
  await page.waitForTimeout(900);
  out.lookupDeva = {
    grammarCards: await page.locator(".word-lookup .pcard").count(),
    mwHeads: await page.locator(".word-lookup .wl-mw").count(),
    greekGlyphs: GREEK.test(await page.locator(".word-lookup").innerText()),
    iastEcho: await page.locator(".word-lookup .feat-iast").first().innerText().catch(() => ""),
  };
  await wl.fill("rāma");
  await page.waitForTimeout(900);
  out.lookupIast = { grammarCards: await page.locator(".word-lookup .pcard").count(),
    mwHeads: await page.locator(".word-lookup .wl-mw").count(),
    greekGlyphs: GREEK.test(await page.locator(".word-lookup").innerText()) };

  // ---- 2. dictionary drawer de-Greeked (placeholder + LSJ gone) ----
  await page.goto(BASE + "/#/bhagavadgita", { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".unit-scripts .w", { timeout: 20000 });
  await page.getByRole("button", { name: "Lexicon" }).first().click().catch(() => {});
  await page.waitForTimeout(400);
  const lexInput = page.locator(".lex-search");
  out.drawer = { visible: await lexInput.isVisible().catch(() => false),
    placeholder: await lexInput.getAttribute("placeholder").catch(() => "") };
  if (out.drawer.visible) {
    await lexInput.fill("धर्म");
    await page.waitForTimeout(1000);
    const txt = await page.locator("#app, body").first().innerText();
    const drawerTxt = await page.locator(".drawer.left").innerText().catch(() => "");
    out.drawer.greek = GREEK.test(drawerTxt);
    out.drawer.cards = await page.locator(".drawer.left .lex-card").count();
    out.drawer.mwTags = await page.locator(".drawer.left .lex-src", { hasText: "MW" }).count();
  }
  await page.keyboard.press("Escape");

  // ---- 3. word-click panel: dual tags laṅ (लङ्), MW heading, compound rows ----
  const w = page.locator(".unit-scripts .w").nth(3);
  await w.click();
  await page.waitForTimeout(1200);
  const panel = page.locator(".side-panel");
  const ptxt = await panel.innerText();
  out.panel = {
    greek: GREEK.test(ptxt),
    lsjGone: !/LSJ/.test(ptxt),
    mwHeading: /Monier-Williams/.test(ptxt),
    featIast: await panel.locator(".feat-iast").count(),
    lemmaStacks: await panel.locator(".lemma-stack").count(),
  };
  // find a laT/laG-style verb tag rendered as IAST primary + deva secondary
  out.panel.dualSample = await panel.locator(".feat-dual").first().innerText()
    .catch(() => "");
  await page.keyboard.press("Escape");

  // ---- 4. samāsa coverage on Raghuvamsa page 1 ----
  await page.goto(BASE + "/#/raghuvamsa", { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".unit-scripts .w", { timeout: 20000 });
  await page.waitForTimeout(2500); // member glosses settle
  const compStats = await page.evaluate(() => {
    const blocks = document.querySelectorAll(".compound");
    let members = 0, glossed = 0, nogloss = 0;
    blocks.forEach((b) => {
      b.querySelectorAll(".comp-member").forEach((m) => {
        members += 1;
        const g = m.querySelector(".comp-gloss")?.textContent ?? "";
        if (!g || g === "…") {} else if (g === "无词条") nogloss += 1;
        else glossed += 1;
      });
    });
    return { blocks: blocks.length, members, glossed, nogloss };
  });
  // sample 10 compound tokens by clicking words that have .compound in col
  out.compoundPage1 = compStats;

  // expanded view: click Expand all then count again
  await page.getByRole("button", { name: "Expand all" }).click().catch(() => {});
  await page.waitForTimeout(2000);
  out.compoundExpanded = await page.evaluate(() => document.querySelectorAll(".compound").length);

  // ---- 5. sidebar: gaṇḍavyuha defaults to 侧栏; drag persists ----
  await page.goto(BASE + "/#/gandavyuha", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1500);
  out.gv = {
    sidebarOn: await page.evaluate(() => document.body.classList.contains("sidebar-view")),
    ctlVisible: await page.locator(".view-ctl").isVisible().catch(() => false),
    sidebarPressed: await page.locator(".view-ctl [aria-label] , .view-ctl button[title*='sidebar']").first().getAttribute("aria-pressed").catch(() => null),
    rows: await page.locator(".tr-sidebar .sb-row").count(),
    credit: await page.locator(".tr-sidebar-credit").innerText().catch(() => ""),
  };
  // drag divider left by ~120px
  const div = page.locator(".sb-divider");
  if (await div.isVisible()) {
    const bb = await div.boundingBox();
    await page.mouse.move(bb.x + bb.width / 2, bb.y + 300);
    await page.mouse.down();
    await page.mouse.move(bb.x - 120, bb.y + 300, { steps: 8 });
    await page.mouse.up();
    await page.waitForTimeout(300);
    out.gv.widthAfterDrag = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue("--sb-w"));
    // persistence across reload
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1200);
    out.gv.widthAfterReload = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue("--sb-w"));
    out.gv.stillSidebar = await page.evaluate(() =>
      document.body.classList.contains("sidebar-view"));
  }

  // ---- 6. BhG regression: interline default, inline zh layer intact ----
  await page.goto(BASE + "/#/bhagavadgita", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1200);
  out.bhg = {
    sidebarOff: await page.evaluate(() => !document.body.classList.contains("sidebar-view")),
    ctlVisible: await page.locator(".view-ctl").isVisible().catch(() => false),
    parseCols: await page.locator(".parse-row .pcol").count(),
  };

  // ---- 7. lang toggle sublabels + bhagavata badge ----
  await page.goto(BASE + "/#/", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(800);
  out.toggle = {
    sublabels: await page.locator(".lang-btn-latin").allInnerTexts(),
  };
  await page.goto(BASE + "/#/bhagavata-02", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1000);
  out.bhagavata = {
    badgeInControls: await page.locator(".controls .no-trans-badge").innerText().catch(() => ""),
    noteText: await page.locator(".tr-none-note").innerText().catch(() => ""),
  };

  console.log(JSON.stringify(out, null, 2));
  await browser.close();
}

main().catch((e) => { console.error(e); process.exit(1); });

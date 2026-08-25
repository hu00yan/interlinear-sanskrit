// Three-tier translation taxonomy verification (2026-08):
//   tier 1 dual (saddharmapundarika)  → no badge, EN default, no zh stream
//   tier 2 zh-only (gandavyuha)       → no badge, 汉译 default + credit, zh rows
//   tier 3 none (bhagavata-01)        → 「无译文」 badge + 此卷暂无可用译文
import { chromium } from "playwright";

const BASE = "http://localhost:4176";
const results = [];
const check = (name, ok, detail) => {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const CHROMIUM = process.env.CHROMIUM_BIN ||
  `${process.env.HOME}/Library/Caches/ms-playwright/chromium_headless_shell-1187/chrome-mac/headless_shell`;
const browser = await chromium.launch({ executablePath: CHROMIUM });
try {
  // ---------- tier 2: #/gandavyuha ----------
  let ctx = await browser.newContext();
  let page = await ctx.newPage();
  await page.goto(`${BASE}/#/gandavyuha`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("[data-ref]", { timeout: 20000 });
  await page.waitForTimeout(2500); // lazy trans-zh fetch + paint

  const badgeG = await page.locator(".no-trans-badge").count();
  check("gandavyuha: no 「无译文」 badge", badgeG === 0, `count=${badgeG}`);

  const noteG = await page.locator("p.tr-none-note").count();
  check("gandavyuha: no 「此卷暂无可用译文」 note", noteG === 0, `count=${noteG}`);

  const zhPressed = await page
    .locator('.tl-ctl button[aria-pressed="true"]')
    .innerText()
    .catch(() => "(none)");
  check(
    "gandavyuha: layer control defaults 汉译",
    zhPressed.includes("汉译"),
    `pressed=${zhPressed}`,
  );

  // sidebar view is the default for partial-alignment works — the zh stream
  // lives there; interline rows are suppressed while it owns the stream.
  const sbCredit = await page.locator(".tr-sidebar-credit").innerText().catch(() => "");
  const sbRowsZh = await page.locator(".tr-sidebar-body .tr-unit").count();
  const sbEmpty = await page.locator(".tr-sidebar-body .lex-hint-empty").count();
  check(
    "gandavyuha: sidebar zh stream visible with 般若·798 credit",
    sbRowsZh > 0 && sbEmpty === 0 && /般若/.test(sbCredit) && /798/.test(sbCredit),
    `rows=${sbRowsZh} emptyNote=${sbEmpty} credit="${sbCredit}"`,
  );

  // flip to 行间 (interline): inline zh tl-lines must paint + credit shows
  await page.locator('.view-ctl button:has-text("行间")').click();
  await page.waitForTimeout(1500);
  const tlLines = await page.locator('[data-tl="zh"] .tl-line').count();
  const enBtnHidden = await page.locator('.tl-ctl button:has-text("英译")').isHidden().catch(() => false);
  check(
    "gandavyuha: interline mode paints inline 汉译 lines",
    tlLines > 0,
    `tl-lines=${tlLines}`,
  );
  check(
    "gandavyuha: dead 英译 segment hidden",
    enBtnHidden,
  );
  await ctx.close();

  // ---------- tier 3: #/bhagavata-01 ----------
  ctx = await browser.newContext();
  page = await ctx.newPage();
  await page.goto(`${BASE}/#/bhagavata-01`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("[data-ref]", { timeout: 20000 });
  await page.waitForTimeout(800);
  const badgeB = await page.locator(".controls .no-trans-badge").count();
  const noteB = await page.locator("p.tr-none-note").innerText().catch(() => "");
  check(
    "bhagavata-01: 「无译文」 badge still present",
    badgeB === 1,
    `count=${badgeB}`,
  );
  check(
    "bhagavata-01: 「此卷暂无可用译文」 notice present",
    noteB.includes("暂无可用译文"),
    `note="${noteB}"`,
  );
  await ctx.close();

  // ---------- tier 1: #/saddharmapundarika ----------
  ctx = await browser.newContext();
  page = await ctx.newPage();
  await page.goto(`${BASE}/#/saddharmapundarika`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("[data-ref]", { timeout: 20000 });
  await page.waitForTimeout(800);
  const badgeS = await page.locator(".no-trans-badge").count();
  const pressedS = await page
    .locator('.tl-ctl button[aria-pressed="true"]')
    .innerText()
    .catch(() => "(none)");
  const enVisibleS = await page.locator('.tl-ctl button:has-text("英译")').isVisible();
  check("saddharmapundarika (dual): no badge", badgeS === 0, `count=${badgeS}`);
  check(
    "saddharmapundarika (dual): defaults 英译, both segments visible",
    pressedS.includes("英译") && enVisibleS,
    `pressed=${pressedS}`,
  );

  // home page regression: badges only on untranslated cards
  await page.goto(`${BASE}/#/`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".work-card, .work-link, a[href*='gandavyuha']", { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(500);
  const gCardBadge = await page
    .locator("a[href='#/gandavyuha'] .no-trans-badge, a[href$='gandavyuha'] .no-trans-badge")
    .count();
  const bhaCardBadge = await page
    .locator("a[href='#/bhagavata-01'] .no-trans-badge, a[href$='bhagavata-01'] .no-trans-badge")
    .count();
  check("home: gandavyuha card has no badge", gCardBadge === 0, `count=${gCardBadge}`);
  check("home: bhagavata-01 card keeps badge", bhaCardBadge === 1, `count=${bhaCardBadge}`);
} finally {
  await browser.close();
}
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
process.exit(failed.length ? 1 : 0);

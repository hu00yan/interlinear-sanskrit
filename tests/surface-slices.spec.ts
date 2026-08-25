// Perf verification: surface-index slicing (lazy per-letter / per-work
// morph lookup). Run against the vite preview server on :4189.
// Asserts: no _surface_index.json fetch, only small _surface slices on the
// wire, parses render, word-click panel intact, zero console errors.
import { expect, test } from "@playwright/test";

const BASE = "http://localhost:4189";
test.use({
  launchOptions: {
    executablePath:
      "/Users/huyan00/Library/Caches/ms-playwright/chromium-1187/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
  },
});

interface Fetch {
  url: string;
  bytes: number;
}

async function track(page: import("@playwright/test").Page): Promise<{
  fetches: Fetch[];
  errors: string[];
}> {
  const fetches: Fetch[] = [];
  const errors: string[] = [];
  page.on("response", async (res) => {
    const u = res.url();
    if (/_surface|\/morph\//.test(u)) {
      let bytes = -1;
      try {
        bytes = (await res.body()).length;
      } catch {
        /* body unavailable (e.g. 404) */
      }
      fetches.push({ url: u.replace(BASE, ""), bytes });
    }
  });
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push(String(e)));
  return { fetches, errors };
}

async function openReader(
  page: import("@playwright/test").Page,
  workId: string,
): Promise<void> {
  await page.goto(`${BASE}/#/${workId}`);
  // first rendered row (verse ".line" / prose ".unit")
  await expect(page.locator(".line, .unit").first()).toBeVisible({
    timeout: 20_000,
  });
}

test("surface slices: Meghadūta lazy lookup, parse columns, word panel", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const { fetches, errors } = await track(page);
  // dual-script mode so Devanagari tokens are mounted (same setup as
  // tests/local-verify.spec.ts — needs a full reload to take effect)
  await page.goto(`${BASE}/#/meghaduta`);
  await page.evaluate(() =>
    localStorage.setItem(
      "interlinear-sanskrit.display",
      JSON.stringify({ iast: true, deva: true }),
    ),
  );
  await page.reload();
  // first rendered row (verse ".line" / prose ".unit")
  await expect(page.locator(".line, .unit").first()).toBeVisible({
    timeout: 20_000,
  });
  const monolith = fetches.filter((f) => f.url.includes("_surface_index"));
  expect(monolith, "monolith must NOT be fetched").toEqual([]);
  const slices = fetches.filter((f) => f.url.includes("_surface"));
  expect(slices.length, "at least one slice fetched").toBeGreaterThan(0);
  const total = slices.reduce((s, f) => s + Math.max(f.bytes, 0), 0);
  console.log(
    `[meghaduta] slice fetches: ${JSON.stringify(slices)} total=${total}B`,
  );

  // parse columns actually render (interlinear cards under words)
  await expect(page.locator(".pcol").first()).toBeVisible();
  const cards = page.locator(".pcard");
  await expect(cards.first()).toBeVisible({ timeout: 15_000 });
  expect(await cards.count()).toBeGreaterThan(5);

  // word-click lexicon panel unchanged: click through a few Devanagari
  // tokens until the MW section appears (exercises the scope-less
  // letter-slice fallback path in surfaceKey)
  const panel = page.locator("aside.side-panel");
  const toks = page.locator(".w.deva-line");
  const n = Math.min(await toks.count(), 6);
  expect(n, "devanagari tokens mounted").toBeGreaterThan(0);
  let mwSeen = false;
  for (let i = 0; i < n && !mwSeen; i++) {
    await toks.nth(i).click();
    await expect(panel).toBeVisible();
    try {
      await expect(
        panel.locator('h3.mw-head:text-is("Monier-Williams")'),
      ).toBeVisible({ timeout: 8_000 });
      mwSeen = true;
    } catch {
      await page.keyboard.press("Escape");
    }
  }
  expect(mwSeen, "Monier-Williams section reached via letter slice").toBe(true);
  expect(errors, "no console errors").toEqual([]);
});

test("surface slices: Rāmāyaṇa + BhG regression", async ({ page }) => {
  test.setTimeout(150_000);
  for (const workId of ["ramayana", "bhagavadgita"]) {
    const { fetches, errors } = await track(page);
    await openReader(page, workId);
    const monolith = fetches.filter((f) => f.url.includes("_surface_index"));
    expect(monolith, `${workId}: monolith must NOT be fetched`).toEqual([]);
    const slices = fetches.filter((f) => f.url.includes("_surface"));
    const total = slices.reduce((s, f) => s + Math.max(f.bytes, 0), 0);
    console.log(`[${workId}] slice fetches: ${JSON.stringify(slices)} total=${total}B`);
    await expect(page.locator(".pcard").first()).toBeVisible({
      timeout: 15_000,
    });
    expect(await page.locator(".pcard").count()).toBeGreaterThan(3);
    expect(errors, `${workId}: no console errors`).toEqual([]);
  }
});

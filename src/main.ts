// Hash router: '' → home (catalog), '#/<workId>?ref=' → reader (work ids are
// globally unique in the catalog), '#/about' → about.
// Pali works live under their own lower route: '#/pali/' (home) and
// '#/pali/<workId>' (reader); legacy bare '#/pali-…' ids redirect there.
// Legacy '#/tlgNNNN/<workId>' routes redirect silently to the new form.
// best-effort onto catalog ids.
import "./style.css";
import {
  catalogLang, hasTranslation, loadCatalog, loadPart, workRoute,
  type CatalogAuthor, type CatalogWork, type Unit,
} from "./api";
import {
  genreFor, hidePanel, mergeCtx, prepare, renderControls, renderUnits,
  tallyLemmas, type RenderCtx,
} from "./render";
import { openTranslation } from "./translation";
import { attachDrawerResize, initDrawerWidth } from "./drawer-resize";
import { lexiconButton } from "./lexicon";
import { renderAbout, aboutLink } from "./about";
import { initPWA } from "./pwa";
import { renderHome } from "./home";
import {
  continueReadingSection, getRecent, saveRecent, setUnitContext,
} from "./bookmarks";
import { setupTranslationLayer, type TlLayerHandle } from "./zh-layer";
import { setupSidebar, type SidebarHandle } from "./sidebar";

const app = document.getElementById("app") as HTMLElement;

// -- drawer resize: shared implementation in src/drawer-resize.ts ---------------
// Both drawers (lexicon left / translation right) share ONE --drawer-width var
// and ONE pointer-event drag implementation (consolidated; previously two
// drifting copies lived here and in translation.ts).
initDrawerWidth();
// Watch for drawer creation (lexicon creates lazily) and attach handles
const drawerObserver = new MutationObserver(() => {
  const left = document.querySelector(".drawer.left") as HTMLElement | null;
  if (left) attachDrawerResize(left, "left");
  const right = document.getElementById("tr-drawer") as HTMLElement | null;
  if (right) attachDrawerResize(right, "right");
});
drawerObserver.observe(document.body, { childList: true, subtree: true });
// also periodically check (fallback for race)
setInterval(() => {
  const left = document.querySelector(".drawer.left") as HTMLElement | null;
  if (left && !left.querySelector(".resize-handle")) attachDrawerResize(left, "left");
  const right = document.getElementById("tr-drawer") as HTMLElement | null;
  if (right && !right.querySelector(".resize-handle")) attachDrawerResize(right, "right");
}, 1000);

const el = (tag: string, cls?: string, text?: string): HTMLElement => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

const TLG_RE = /^tlg\d{4}$/;
const BATCH_UNITS = 120; // units fetched per part top-up (render pages are smaller)
const PAGE_SIZE = 30; // units rendered per page — keeps scroll manageable

/** Top-level site section: Sanskrit (default, root routes) or Pali
 *  (#/pali/ prefix). */
type Section = "sa" | "pi";

function go(hash: string): void {
  hidePanel();
  const route = hash.replace(/^#\/?/, "");
  if (route === "about") return renderAbout(app);
  setUnitContext(null, null); // star/copy buttons only make sense in a reader
  const [routePart, queryPart] = route.split("?");
  const refParam =
    queryPart ? new URLSearchParams(queryPart).get("ref") ?? undefined
              : undefined;
  // Pali section: '#/pali/' home, '#/pali/<workId>' reader
  if (routePart === "pali") return void goHome("pi");
  if (routePart.startsWith("pali/")) {
    const rest = routePart.slice("pali/".length);
    if (!rest) return void goHome("pi");
    return void openWork(rest, refParam, "pi");
  }
  // modern route: single global-unique work id
  if (routePart && !routePart.includes("/") &&
      !TLG_RE.test(routePart)) {
    return void openWork(routePart, refParam);
  }
  // legacy two-segment routes (#/tlgNNNN/<id> and Greek-era #/<x>/<y>)
  const segs = routePart.split("/");
  if (segs.length === 2) return void redirectLegacy(segs[0], segs[1]);
  void goHome();
}

/** Resolve a work id via the catalog; supports legacy tlg-prefixed pairs. */
async function resolveWork(
  first: string,
  second?: string,
): Promise<{ author: CatalogAuthor; work: CatalogWork } | null> {
  try {
    const catalog = await loadCatalog();
    for (const author of catalog.authors) {
      if (second !== undefined) {
        if (author.key.toLowerCase() === first.toLowerCase()) {
          const w = author.works.find(
            (w) => w.id.toLowerCase() === second.toLowerCase());
          if (w) return { author, work: w };
        }
      } else {
        const w = author.works.find(
          (w) => w.id.toLowerCase() === first.toLowerCase());
        if (w) return { author, work: w };
      }
    }
    // best-match fallback: unique work-id suffix/prefix match
    for (const author of catalog.authors) {
      const w = author.works.find((w) =>
        second === undefined
          ? w.id.toLowerCase().startsWith(first.toLowerCase())
          : w.id.toLowerCase() === second.toLowerCase());
      if (w) return { author, work: w };
    }
  } catch { /* catalog unavailable */ }
  return null;
}

async function openWork(
  workId: string,
  refParam?: string,
  section: Section = "sa",
): Promise<void> {
  const found = await resolveWork(workId);
  if (!found) {
    app.replaceChildren(el("p", "crumbs", `Unknown work ${workId}.`));
    return;
  }
  // Legacy bare-id route to a Pali work: canonical home is #/pali/<id>.
  // (Preserves any ?ref= deep link across the redirect.)
  if (section !== "pi" && catalogLang(found.work, found.author) === "pi") {
    location.hash = workRoute(found.work) +
      (refParam ? `?ref=${encodeURIComponent(refParam)}` : "");
    return;
  }
  return openReader(found.author.key, found.work.id, refParam, section);
}

/* ---------------- home ---------------- */

function goHome(section: Section = "sa"): void {
  document.title = section === "pi" ? "Pali Reader" : "Sanskrit Reader";
  renderHome(app, section);
  // "Continue reading" above the starter suggestions (home.ts not touched)
  const titles = new Map<string, string>();
  const sec = continueReadingSection(titles);
  if (!sec.hidden) {
    app.querySelector(".starters")?.before(sec);
    void loadCatalog().then((catalog) => {
      for (const author of catalog.authors) {
        for (const w of author.works) titles.set(w.id, w.title);
      }
      sec.replaceWith(continueReadingSection(titles));
    }).catch(() => {});
  }
}

async function redirectLegacy(first: string, second: string): Promise<void> {
  // Silent best-match: exact tlg+id pair, else bare id match, else home.
  const found = await resolveWork(
    TLG_RE.test(first) ? first : second ?? "",
    TLG_RE.test(first) ? second : undefined);
  location.hash = found ? `#/${found.work.id}` : "";
}

/* ---------------- reader ---------------- */

interface PageInfo {
  rows: number; // DOM rows appended for this page (1 per unit)
}
interface ReaderState {
  work: CatalogWork;
  author: CatalogAuthor;
  queue: string[];       // part file paths not yet fetched
  buffer: Unit[];        // fetched but not yet rendered
  kind: "verse" | "prose";
  ctx: RenderCtx;
  body: HTMLElement;
  pager: {
    root: HTMLElement;
    info: HTMLElement;
    prev: HTMLButtonElement;
    next: HTMLButtonElement;
    jump: HTMLInputElement;
  };
  pages: PageInfo[];     // rendered pages, in order
  busy: boolean;
  atEnd: boolean;
  renderedUnits: number;
  /** Set once the "no morph coverage" notice has been considered. */
  morphNoteDone?: boolean;
  /** Chinese translation layer when this work ships translationZh
   *  (null/absent otherwise — no DOM impact). */
  tl?: TlLayerHandle | null;
  /** Sidebar translation view handle (null when no translation ships). */
  sb?: SidebarHandle | null;
}

const PAGE_UNITS = PAGE_SIZE;

function totalPages(state: ReaderState): number {
  return Math.max(1, Math.ceil(state.work.unitCount / PAGE_UNITS));
}

function updatePager(state: ReaderState): void {
  const p = state.pages.length;
  const start = p ? state.renderedUnits - state.pages[p - 1].rows + 1 : 0;
  const end = state.renderedUnits;
  const total = state.work.unitCount;
  state.pager.info.textContent =
    `Units ${start.toLocaleString()}–${end.toLocaleString()} of ` +
    `${total.toLocaleString()} · Page ${p} of ${totalPages(state)}`;
  state.pager.prev.disabled = state.busy || p <= 1;
  state.pager.next.disabled =
    state.busy || state.atEnd || end >= total;
}

async function openReader(
  authorKey: string,
  workId: string,
  refParam?: string,
  section: Section = "sa",
): Promise<void> {
  allUnits = [];
  app.replaceChildren();
  app.appendChild(el("p", "crumbs", "Loading…"));

  let author: CatalogAuthor | undefined;
  let work: CatalogWork | undefined;
  try {
    const catalog = await loadCatalog();
    author = catalog.authors.find((a) => a.key === authorKey);
    work = author?.works.find((w) => w.id === workId);
  } catch (e) {
    app.replaceChildren(el("p", "unparsed-note",
      `Failed to load catalog: ${(e as Error).message}`));
    return;
  }
  if (!author || !work) {
    app.replaceChildren(el("p", "unparsed-note",
      `Unknown work ${authorKey}/${workId}.`));
    return;
  }

  const controls = renderControls(`${author.name}, ${work.title}`,
    () => (location.hash = section === "pi" ? "#/pali/" : ""),
    // text-only works: 「无译文」 badge beside the crumbs
    { noTranslation: !hasTranslation(work) });
  document.title = section === "pi"
    ? `${work.title} · Pali Reader`
    : `${work.title} · Sanskrit Reader`;
  app.replaceChildren(controls.root);

  // translation toggle only when the catalog ships translations
  // readerState is assigned below; closure captures live reference for speaker parity
  let readerState: ReaderState | null = null;
  if ((work as { translation?: { files?: string[] } }).translation
    ?.files?.length) {
    let trView: Awaited<ReturnType<typeof openTranslation>> = null;
    const trBtn = el("button", "tr-toggle", "English ▭") as HTMLButtonElement;
    trBtn.type = "button";
    trBtn.title = "Toggle the English translation drawer";
    trBtn.setAttribute("aria-pressed", "false");
    trBtn.addEventListener("click", async () => {
      if (!trView) {
        trView = await openTranslation(work!, () => allUnits, readerState?.ctx);
        if (!trView) return;
        // keep the toggle honest no matter HOW the drawer closes
        // (Esc / outside click / sticky close all dispatch "tr-closed")
        trView.root.addEventListener("tr-closed", () => {
          trBtn.setAttribute("aria-pressed", "false");
        });
        trBtn.setAttribute("aria-pressed", String(trView.isOpen()));
        return;
      }
      trView.toggle();
      trBtn.setAttribute("aria-pressed", String(trView.isOpen()));
    });
    controls.root.appendChild(trBtn);
  }

  const body = el("div");
  // Text-only works: say ONCE, up front, that no translation row will
  // appear — instead of silently omitting the translation area.
  if (!hasTranslation(work)) {
    const note = el("p", "tr-none-note", "此卷暂无可用译文");
    note.lang = "zh";
    app.appendChild(note);
  }
  app.appendChild(body);

  // pager footer replaces the bare Load-more button
  const info = el("span", "pager-info");
  const prev = el("button", undefined, "← Prev") as HTMLButtonElement;
  const next = el("button", undefined, "Next →") as HTMLButtonElement;
  prev.type = next.type = "button";
  const jump = el("input") as HTMLInputElement;
  jump.type = "number";
  jump.min = "1";
  jump.placeholder = "Page";
  jump.setAttribute("aria-label", "Jump to page");
  const pagerRoot = el("div", "pager");
  pagerRoot.appendChild(info);
  // prev / jump / next share one joined control cluster (see .pager-group)
  const group = el("span", "pager-group");
  group.appendChild(prev);
  group.appendChild(jump);
  group.appendChild(next);
  pagerRoot.appendChild(group);

  const state: ReaderState = {
    work, author,
    queue: [...work.files],
    buffer: [],
    kind: "verse",
    ctx: { morph: new Map(), gloss: new Map(), genre: genreFor(author.key),
      authorKey: author.key, lang: catalogLang(work, author) },
    body,
    pager: { root: pagerRoot, info, prev, next, jump },
    pages: [],
    busy: false,
    atEnd: false,
    renderedUnits: 0,
  };
  readerState = state;
  // Chinese translation layer (英译⇄汉译 segmented control): appears ONLY when
  // this catalog work carries translationZh — otherwise setupTranslationLayer
  // returns null and the page renders exactly as before (regression-critical).
  state.tl = setupTranslationLayer(work, {
    controls: controls.root,
    anchor: () => body,
    getBody: () => state.body,
  });
  // 行间 | 侧栏 view-mode control + draggable translation sidebar
  // (no-ops entirely on works without any translation)
  state.sb = setupSidebar(work, {
    controls: controls.root,
    getBody: () => state.body,
    getUnits: () => allUnits,
    tl: state.tl,
  });
  prev.addEventListener("click", () => void turnPage(state, -1));
  next.addEventListener("click", () => void turnPage(state, +1));
  jump.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    const target = Math.min(totalPages(state),
      Math.max(1, parseInt(jump.value || "1", 10) || 1));
    jump.value = String(target);
    void turnPage(state, target - state.pages.length);
  });

  await loadNextPage(state);
  app.appendChild(pagerRoot);
  updatePager(state);

  setUnitContext(authorKey, workId); // per-unit ★ / copy-link buttons

  // resume: honor an explicit ?ref= deep link by paging forward to it
  if (refParam) {
    await jumpToRef(state, refParam);
  }
  // record position immediately so "Continue reading" has fresh data
  saveRecent(authorKey, workId,
    state.body.querySelector<HTMLElement>("[data-ref]")?.dataset.ref ?? "");

  // track reading position on scroll (debounced; topmost visible unit wins)
  let saveTimer = 0;
  const onScrollSave = (): void => {
    window.clearTimeout(saveTimer);
    saveTimer = window.setTimeout(() => {
      if (!location.hash.startsWith(`#/${authorKey}/${workId}`)) return;
      const rows = state.body.querySelectorAll<HTMLElement>("[data-ref]");
      for (const r of Array.from(rows)) {
        if (r.getBoundingClientRect().bottom < 0) continue;
        saveRecent(authorKey, workId, r.dataset.ref!);
        break;
      }
    }, 900);
  };
  window.addEventListener("scroll", onScrollSave, { passive: true });

}

/** All Greek units currently on screen (translation alignment source). */
let allUnits: Unit[] = [];

/** Page forward until the unit with this ref is rendered, then center it.
 *  Capped at ~40 pages (1200 units) so a bogus ref cannot load a whole work. */
async function jumpToRef(
  state: ReaderState,
  ref: string,
): Promise<void> {
  const find = (): HTMLElement | null =>
    state.body.querySelector<HTMLElement>(
      `[data-ref="${CSS.escape(ref)}"]`,
    );
  let target = find();
  let guard = 0;
  while (!target && !state.atEnd && guard < 40) {
    await loadNextPage(state);
    updatePager(state);
    target = find();
    guard += 1;
  }
  if (!target) return;
  target.scrollIntoView({ block: "center" });
  target.classList.add("ref-flash");
  window.setTimeout(() => target!.classList.remove("ref-flash"), 2400);
}

/** Render exactly one more page (fetching as needed). */
async function loadNextPage(state: ReaderState): Promise<void> {
  try {
    while (state.buffer.length < PAGE_UNITS && state.queue.length) {
      const part = await loadPart(state.queue.shift()!);
      state.kind = state.kind === "prose" ? "prose"
        : part.kind === "prose" ? "prose" : state.kind;
      state.buffer.push(...part.units);
    }
    if (!state.buffer.length) {
      state.atEnd = true;
      return;
    }
    const batch = state.buffer.splice(0, PAGE_UNITS);
    // Pali works skip the Devanagari morph pipeline — no slice to fetch.
    const scope = catalogLang(state.work, state.author) === "pi"
      ? undefined
      : state.work.id;
    const freshCtx = await prepare(batch, scope);
    mergeCtx(state.ctx, freshCtx.morph, freshCtx.gloss);
    // Morph coverage currently spans the Bhagavadgītā analysis only; other
    // works would render mostly silent "—" columns. Say so once, explicitly,
    // whenever fewer than half of this page's distinct forms have analyses.
    if (!state.morphNoteDone) {
      state.morphNoteDone = true;
      const forms = new Set(batch.flatMap((u) => u.words));
      const covered = [...forms]
        .filter((f) => (freshCtx.morph.get(f)?.length ?? 0) > 0).length;
      if (forms.size > 0 && covered / forms.size < 0.5) {
        state.body.appendChild(el(
          "div",
          "morph-empty-note",
          "本卷语法解析覆盖有限（现有完整解析仅覆盖《薄伽梵歌》，其余卷目陆续补充中），未解析的词以“—”标示。点击任意单词仍可查询词典。",
        ));
      }
    }
    tallyLemmas(state.ctx, batch); // grow the work-view frequency signal
    renderUnits(state.body, batch, state.ctx, state.kind,
      state.renderedUnits);
    allUnits.push(...batch);
    state.pages.push({ rows: batch.length });
    state.renderedUnits += batch.length;
    void state.tl?.sync(); // paint/clear zh lines on freshly rendered rows
    void state.sb?.refresh(); // sidebar stream follows newly rendered pages
  } catch (e) {
    state.pager.info.textContent = `Load failed: ${(e as Error).message}`;
    state.atEnd = true;
  }
}

/** Remove the last rendered page from screen and memory. */
function popPage(state: ReaderState): void {
  const last = state.pages.pop();
  if (!last) return;
  for (let i = 0; i < last.rows; i++) {
    state.body.lastElementChild?.remove();
  }
  allUnits.length -= last.rows;
  state.renderedUnits -= last.rows;
}

/** Page turning: delta ±1 steps or a positive jump target. */
async function turnPage(
  state: ReaderState,
  delta: number,
): Promise<void> {
  if (state.busy || !delta) return;
  const cur = state.pages.length;
  const target = Math.max(1,
    Math.min(totalPages(state), cur + delta));
  if (target === cur) return;
  state.busy = true;
  updatePager(state);
  try {
    if (delta > 0) {
      while (state.pages.length < target && !state.atEnd) {
        await loadNextPage(state);
      }
    } else {
      while (state.pages.length > target && state.pages.length > 1) {
        popPage(state);
      }
    }
    window.scrollTo({ top: 0 });
  } finally {
    state.busy = false;
    updatePager(state);
  }
}

window.addEventListener("hashchange", () => go(location.hash));
initPWA(); // service worker + offline badge (see pwa.ts)
// floating Lexicon trigger: guarantees the drawer on every route,
// including paste (whose page module is not owned by the UI round)
const lexFab = lexiconButton("Lexicon");
lexFab.className = "lex-fab";
document.body.appendChild(lexFab);
go(location.hash);

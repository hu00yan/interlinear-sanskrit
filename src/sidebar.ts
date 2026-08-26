// Sidebar translation view (侧栏): the translation stream as a FIXED RIGHT
// COLUMN beside the reader, instead of inline rows between the source and
// the parse cards (行间). Chosen per work via the 「行间 | 侧栏」 segmented
// control in the toolbar; works whose Chinese translation only partially
// aligns (translationZh.alignment === "partial", e.g. Gaṇḍavyūha) DEFAULT
// to 侧栏 because anchored insertions interrupt reading flow.
//
// The stream follows the current 英译/汉译 toggle (zh-layer's localStorage
// mode + its "tl-mode" window event); a layer that this work doesn't ship
// falls back to the other one. The divider is DRAGGABLE (pointer events,
// min 240px / max 50vw) and the width is remembered PER WORK. Inline zh
// lines are suppressed while 侧栏 is active so the translation never
// renders twice.
import { type CatalogWork, type Unit } from "./api";
import { loadTranslationUnits } from "./translation";
import { loadZhMap, translationZhOf } from "./zh-layer";

type El = HTMLElement;
const el = (tag: string, cls?: string, text?: string): El => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text; // never innerHTML
  return e;
};

export type ViewMode = "interline" | "sidebar";

const modeKey = (id: string): string => `reader-view:${id}`;

/** Per-work stored view mode; null when the reader never chose one. */
function storedMode(workId: string): ViewMode | null {
  try {
    const v = localStorage.getItem(modeKey(workId));
    return v === "sidebar" || v === "interline" ? v : null;
  } catch {
    return null;
  }
}

/** Default: 侧栏 for partially-aligned Chinese translations (anchored
 *  insertions interrupt reading flow), 行间 otherwise. */
export function defaultViewMode(work: CatalogWork): ViewMode {
  const zh = (work as { translationZh?: { alignment?: unknown } })
    .translationZh;
  return zh && zh.alignment === "partial" ? "sidebar" : "interline";
}

const MIN_W = 240;

function clampWidth(px: number): number {
  return Math.max(MIN_W, Math.min(window.innerWidth * 0.5, px));
}

export interface SidebarHandle {
  mode(): ViewMode;
  setMode(m: ViewMode): void;
  /** Re-paint after freshly rendered pages (call like tl.sync()). */
  refresh(): Promise<void>;
  /** Full teardown for route changes: removes the sidebar DOM, listeners
   *  and body state; the remembered width dies with this work session. */
  destroy(): void;
}

/** The ONE active sidebar instance's teardown (main.ts calls it before any
 *  route render so a 侧栏 left open on work A can never leak onto work B,
 *  home, or about). */
let activeTeardown: (() => void) | null = null;

export function setupSidebar(
  work: CatalogWork,
  opts: {
    controls: El;
    getBody: () => El | null;
    getUnits: () => Unit[];
    /** Inline zh-layer handle — suppressed while the sidebar owns the
     *  translation stream (optional; absent when no translationZh). */
    tl?: { setSuppressed(b: boolean): void } | null;
  },
): SidebarHandle | null {
  const enMeta = (work as {
    translation?: { files?: unknown };
  }).translation;
  const enFiles = enMeta && Array.isArray(enMeta.files)
    ? enMeta.files.filter((f): f is string => typeof f === "string")
    : [];
  const zhMeta = translationZhOf(work);
  const zhFiles = (zhMeta?.files as unknown[] | undefined)?.filter(
    (f): f is string => typeof f === "string",
  ) ?? [];
  // zh-only works (Gaṇḍavyūha…) qualify too — English is not required
  if (!enFiles.length && !zhFiles.length) return null;

  let mode: ViewMode = storedMode(work.id) ?? defaultViewMode(work);
  // translation layer preference (mirrors zh-layer storage)
  let layer: "en" | "zh" = (() => {
    try {
      return localStorage.getItem(`tl-layer:${work.id}`) === "zh"
        ? "zh"
        : "en";
    } catch {
      return "en";
    }
  })();

  /* ---------------- toolbar control ---------------- */
  const wrap = el("span", "theme-ctl view-ctl");
  wrap.setAttribute("role", "group");
  wrap.setAttribute("aria-label", "Translation layout");
  const btnInline = el("button", undefined, "行间") as HTMLButtonElement;
  const btnSidebar = el("button", undefined, "侧栏") as HTMLButtonElement;
  btnInline.type = btnSidebar.type = "button";
  btnInline.title = "Translation inline between the lines";
  btnSidebar.title = "Translation in a resizable sidebar";
  const paintCtl = (): void => {
    btnInline.setAttribute("aria-pressed", String(mode === "interline"));
    btnSidebar.setAttribute("aria-pressed", String(mode === "sidebar"));
  };
  wrap.append(btnInline, btnSidebar);
  paintCtl();
  opts.controls.appendChild(wrap);

  /* ---------------- sidebar DOM ---------------- */
  let aside: El | null = null;
  let sbBody: El | null = null;
  let creditEl: El | null = null;
  let divider: El | null = null;

  // Width memory lives in THIS closure only — remembered across
  // open/close within the same work view (same work session), never
  // persisted to localStorage, so a later visit starts from the default.
  let sessionWidth: number | null = null;

  function applyWidth(px: number): void {
    sessionWidth = px;
    document.documentElement.style.setProperty("--sb-w", `${Math.round(px)}px`);
  }
  function savedWidth(): number {
    if (sessionWidth !== null) return clampWidth(sessionWidth);
    return Math.min(400, window.innerWidth * 0.38);
  }

  function attachDrag(div: El): void {
    div.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      div.classList.add("dragging");
      div.setPointerCapture(e.pointerId);
      document.body.classList.add("sb-resizing");
      const move = (ev: PointerEvent): void =>
        applyWidth(clampWidth(window.innerWidth - ev.clientX));
      const up = (): void => {
        div.classList.remove("dragging");
        document.body.classList.remove("sb-resizing");
        div.removeEventListener("pointermove", move);
        div.removeEventListener("pointerup", up);
      };
      div.addEventListener("pointermove", move);
      div.addEventListener("pointerup", up);
    });
  }

  function ensureDom(): void {
    if (aside?.isConnected) return;
    aside = el("aside", "tr-sidebar");
    aside.setAttribute("aria-label", "Translation sidebar");
    const head = el("div", "tr-sidebar-head");
    head.appendChild(el("h2", undefined, "译文"));
    creditEl = el("p", "tr-sidebar-credit");
    head.appendChild(creditEl);
    // F1: explicit close control — hides the sidebar entirely (switches
    // back to 行间); reopening within this work view keeps the width.
    const close = el("button", "close-btn sb-close", "✕") as HTMLButtonElement;
    close.type = "button";
    close.setAttribute("aria-label", "Close translation sidebar");
    close.title = "Close sidebar";
    close.addEventListener("click", () => void apply("interline"));
    head.appendChild(close);
    aside.appendChild(head);
    sbBody = el("div", "tr-sidebar-body");
    aside.appendChild(sbBody);
    document.body.appendChild(aside);
    divider = el("div", "sb-divider");
    divider.setAttribute("role", "separator");
    divider.setAttribute("aria-label", "Drag to resize the sidebar");
    document.body.appendChild(divider);
    attachDrag(divider);
    applyWidth(savedWidth());
  }

  /* ---------------- stream painting ---------------- */

  let enTexts: Promise<Array<{ ref: string; text: string }>> | null = null;
  let zhMapP: Promise<Map<string, string> | null> | null = null;

  function effectiveLayer(): "en" | "zh" | null {
    if (layer === "zh") return zhFiles.length ? "zh" : enFiles.length ? "en" : null;
    return enFiles.length ? "en" : zhFiles.length ? "zh" : null;
  }

  function paintCredit(which: "en" | "zh"): void {
    if (!creditEl) return;
    const meta = which === "en"
      ? (work as { translation?: { translator?: string; year?: string | number } | null })
        .translation ?? null
      : zhMeta as { translator?: string; year?: string | number } | null;
    const who = meta?.translator ? String(meta.translator) : "";
    const yr = meta?.year !== undefined && meta.year !== ""
      ? String(meta.year)
      : "";
    creditEl.textContent =
      [which === "en" ? who : `${who}译`, yr].filter(Boolean).join(" · ");
    creditEl.hidden = !creditEl.textContent;
  }

  async function paint(): Promise<void> {
    ensureDom();
    const body = opts.getBody();
    const units = opts.getUnits();
    const box = sbBody!;
    const which = effectiveLayer();
    if (!which || !box) {
      box?.replaceChildren(el("p", "lex-hint-empty", "此卷暂无可用译文"));
      return;
    }
    paintCredit(which);

    const enList = which === "en"
      ? (enTexts ??= loadTranslationUnits(enFiles).catch(() => []))
      : null;
    const zhM = which === "zh"
      ? (zhMapP ??= loadZhMap(zhFiles))
      : null;
    const ens = enList ? await enList : [];
    const zhs = zhM ? await zhM : null;

    if (!box.isConnected) return; // route changed mid-load
    box.replaceChildren();
    const used = new Set<number>();
    units.forEach((u, i) => {
      let j = -1;
      if (u.ref) j = ens.findIndex((t, k) => t.ref === u.ref && !used.has(k));
      if (j < 0 && i < ens.length && !used.has(i)) j = i;
      if (j >= 0) used.add(j);
      let txt = "";
      if (which === "zh") {
        txt = (u.ref && zhs?.get(u.ref)) ||
          (j >= 0 ? ens[j]?.text : "") || "";
        if (!txt && j >= 0 && ens[j]) txt = ens[j]!.text; // en fallback
      } else {
        txt = j >= 0 ? ens[j]?.text ?? "" : "";
      }
      const row = el("div", "tr-unit sb-row");
      row.dataset.i = String(i);
      const refTxt = u.ref || (j >= 0 ? ens[j]?.ref : "") || "";
      if (refTxt) row.appendChild(el("span", "tr-ref", refTxt));
      row.appendChild(el("div", "tr-text", txt || "—"));
      box.appendChild(row);
    });
    syncScroll();
  }

  /* ---------------- scroll sync (ref-index mapping) ---------------- */

  let rafPending = 0;
  function syncScroll(): void {
    rafPending = 0;
    if (!aside || !aside.isConnected || mode !== "sidebar") return;
    const rows = Array.from(
      opts.getBody()?.querySelectorAll<HTMLElement>("[data-ref]") ?? [],
    );
    if (!rows.length || !sbBody) return;
    const fy = window.innerHeight * 0.42;
    let best = -1;
    let bestDist = Infinity;
    rows.forEach((r) => {
      const rc = r.getBoundingClientRect();
      if (rc.bottom < -80 || rc.top > window.innerHeight + 80) return;
      const d = Math.abs(rc.top + rc.height / 2 - fy);
      if (d < bestDist) {
        bestDist = d;
        best = rows.indexOf(r);
      }
    });
    if (best < 0) return;
    const sbRows = sbBody.querySelectorAll<HTMLElement>(".sb-row");
    const target = sbRows[best];
    sbRows.forEach((r, i) => r.classList.toggle("current", i === best));
    if (!target) return;
    const headH =
      aside!.querySelector<HTMLElement>(".tr-sidebar-head")?.offsetHeight ?? 0;
    const tRect = target.getBoundingClientRect();
    const aRect = aside!.getBoundingClientRect();
    const wantY = Math.min(
      Math.max(aRect.top + headH + 4, fy - tRect.height / 2),
      aRect.bottom - tRect.height - 8,
    );
    sbBody.scrollTop += tRect.top - wantY;
  }
  const scheduleSync = (): void => {
    if (!rafPending) rafPending = requestAnimationFrame(syncScroll);
  };
  const onWinScroll = (): void => {
    if (mode === "sidebar") scheduleSync();
  };
  window.addEventListener("scroll", onWinScroll, { passive: true });

  /* ---------------- mode switching ---------------- */

  async function apply(next: ViewMode): Promise<void> {
    mode = next;
    document.body.classList.toggle("sidebar-view", mode === "sidebar");
    paintCtl();
    if (mode === "sidebar") {
      opts.tl?.setSuppressed(true); // no double rendering of the stream
      await paint();
      aside?.classList.remove("hidden");
      divider?.classList.remove("hidden");
      scheduleSync();
    } else {
      opts.tl?.setSuppressed(false);
      aside?.classList.add("hidden"); // kept in DOM, cheap to re-enter
      divider?.classList.add("hidden");
    }
    try {
      localStorage.setItem(modeKey(work.id), mode);
    } catch { /* best-effort */ }
  }

  btnInline.addEventListener("click", () => void apply("interline"));
  btnSidebar.addEventListener("click", () => void apply("sidebar"));

  // follow the 英译/汉译 toggle while open
  const onTlMode = ((e: CustomEvent<string>) => {
    if (e.detail === "en" || e.detail === "zh") {
      layer = e.detail;
      if (mode === "sidebar") void paint();
    }
  }) as EventListener;
  window.addEventListener("tl-mode", onTlMode);

  // restore persisted/default mode lazily but synchronously enough for the
  // first paint (apply() itself is idempotent)
  void apply(mode);

  /** Route-change teardown (F1): nothing of this sidebar may outlive the
   *  work view — DOM, listeners and body squeeze all go; the remembered
   *  width dies with this closure. */
  function destroy(): void {
    if (activeTeardown === destroy) activeTeardown = null;
    window.removeEventListener("scroll", onWinScroll);
    window.removeEventListener("tl-mode", onTlMode);
    aside?.remove();
    divider?.remove();
    document.body.classList.remove("sidebar-view", "sb-resizing");
    aside = null;
    sbBody = null;
    divider = null;
    sessionWidth = null;
  }
  activeTeardown = destroy;

  return {
    mode: () => mode,
    setMode: (m: ViewMode) => void apply(m),
    refresh: async () => {
      if (mode === "sidebar") await paint();
    },
    destroy,
  };
}

/** Called by the router BEFORE rendering any route: tears down whichever
 *  work's sidebar is still attached (no-op when none). */
export function teardownSidebar(): void {
  activeTeardown?.();
  activeTeardown = null;
}

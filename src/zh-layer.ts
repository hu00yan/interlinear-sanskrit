// Chinese translation layer: per-work 英译 ⇄ 汉译 switch for works whose
// catalog entry carries a `translationZh` field. Everything here is written
// DEFENSIVELY — the catalog/files land from a parallel data agent, so any
// absence (missing field, empty files, 404 JSON, malformed units) degrades
// gracefully and never throws into the reader.
//
// Catalog contract (optional, may appear on any work):
//   work.translationZh = { translator?, year?, source?, license?,
//                          files: ["trans-zh/<id>.json"] }
// File contract (mirrors trans/*.json):
//   { workId?, translator?, year?, license?, alignment?: "full"|"partial",
//     note?, units: [{ ref?, text }] }   // refs omitted -> per-unit fallback
//
// Behavior:
//   • Toggle renders ONLY when translationZh.files is non-empty; works
//     without it see zero DOM additions (regression-critical).
//   • Default mode is 英译 (= the pre-existing view); choice persists per
//     work under localStorage "tl-layer:<workId>".
//   • 汉译 mode paints an inline zh line per rendered unit (before the parse
//     row); units without a zh ref fall back to their English text plus a
//     faint 「无汉译」 tag.
//   • trans-zh files load lazily on first 汉译 activation (never on initial
//     page load) and cache in memory; English fallback texts likewise load
//     lazily and only when a unit actually misses its zh ref.
import { fetchJSON, type CatalogWork } from "./api";

type El = HTMLElement;
const el = (tag: string, cls?: string, text?: string): El => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text; // never innerHTML
  return e;
};

export type TlMode = "en" | "zh";

interface ZhMeta {
  translator?: string;
  year?: string | number;
  source?: string;
  license?: string;
  files?: unknown;
}

export interface ZhFile {
  workId?: string;
  translator?: string;
  year?: string | number;
  license?: string;
  alignment?: string;
  note?: string;
  units?: Array<{ ref?: string; text?: string }>;
}

/** Handle handed back to the reader so freshly rendered pages get synced. */
export interface TlLayerHandle {
  /** Idempotent: paints/clears tl-lines over every [data-ref] row. */
  sync(): Promise<void>;
  /** Sidebar view owns the translation stream while active — inline
   *  zh lines are suppressed (and cleared) until re-enabled. */
  setSuppressed(b: boolean): void;
}

const lsKey = (workId: string): string => `tl-layer:${workId}`;

function storedMode(workId: string): TlMode {
  try {
    return localStorage.getItem(lsKey(workId)) === "zh" ? "zh" : "en";
  } catch {
    return "en";
  }
}

function storeMode(workId: string, m: TlMode): void {
  try {
    localStorage.setItem(lsKey(workId), m);
  } catch { /* private mode etc. — persistence is best-effort */ }
  // sidebar (and anything else rendering the translation stream) follows
  window.dispatchEvent(new CustomEvent("tl-mode", { detail: m }));
}

/** ref -> zh text map for this work's trans-zh files (null = unavailable).
 *  Shared with the sidebar view; failures resolve null. */
export function loadZhMap(files: string[]): Promise<Map<string, string> | null> {
  return loadZh(files);
}

/** Defensive extraction: null unless translationZh carries usable files. */
export function translationZhOf(work: CatalogWork): ZhMeta | null {
  const raw = (work as { translationZh?: unknown }).translationZh;
  if (!raw || typeof raw !== "object") return null;
  const meta = raw as ZhMeta;
  if (!Array.isArray(meta.files) || meta.files.length === 0) return null;
  return meta;
}

/* ---------------- lazy loads + in-memory caches ---------------- */

const zhCache = new Map<string, Promise<Map<string, string> | null>>();
const zhMetaCache = new Map<string, ZhFile | null>();

/** ref -> zh text map for this work's trans-zh files (null = unavailable).
 *  Failures are cached too so a missing 404 file doesn't refetch per page. */
function loadZh(files: string[]): Promise<Map<string, string> | null> {
  const key = files.join("|");
  let p = zhCache.get(key);
  if (!p) {
    p = Promise.all(
      files.map((f) => fetchJSON<ZhFile>(`data/${f}`)),
    ).then((parts) => {
      const map = new Map<string, string>();
      for (const part of parts) {
        for (const u of Array.isArray(part?.units) ? part.units : []) {
          if (u && typeof u.ref === "string" && typeof u.text === "string") {
            if (!map.has(u.ref)) map.set(u.ref, u.text);
          }
        }
      }
      return map;
    }).catch(() => null);
    zhCache.set(key, p);
  }
  return p;
}

/** Full metadata of the first parseable zh file (credit source of truth). */
async function loadZhMeta(
  files: string[],
  catalogMeta: ZhMeta,
): Promise<ZhFile | null> {
  const key = files.join("|");
  if (zhMetaCache.has(key)) return zhMetaCache.get(key)!;
  let meta: ZhFile | null = null;
  try {
    meta = await fetchJSON<ZhFile>(`data/${files[0]}`);
  } catch {
    meta = null;
  }
  // catalog fields back-stop missing file metadata
  if (meta && meta.translator === undefined) {
    meta.translator = catalogMeta.translator;
  }
  if (meta && meta.year === undefined) meta.year = catalogMeta.year;
  if (meta && !meta.license) meta.license = catalogMeta.license;
  zhMetaCache.set(key, meta);
  return meta;
}

/** ref -> English text map from the existing trans/*.json files. Loaded
 *  lazily ONLY when a zh-miss needs an English fallback line. */
async function loadEnTexts(
  files: string[],
): Promise<Map<string, string>> {
  const map = new Map<string, string>();
  if (!files.length) return map;
  try {
    const parts = await Promise.all(
      files.map((f) =>
        fetchJSON<{ units?: Array<{ ref?: string; text?: string; w?: string }> }>(
          `data/${f}`,
        )),
    );
    for (const part of parts) {
      for (const u of Array.isArray(part?.units) ? part.units : []) {
        if (!u || typeof u.ref !== "string") continue;
        const txt = typeof u.text === "string"
          ? u.text
          : typeof u.w === "string"
          ? u.w
          : "";
        if (txt && !map.has(u.ref)) map.set(u.ref, txt);
      }
    }
  } catch { /* empty map -> "—" fallback lines */ }
  return map;
}

/* ---------------- credit ---------------- */

/** 「鸠摩罗什译（后秦·402）」 style credit from FILE metadata, falling back
 *  to catalog fields. Never throws; degenerates to "汉译". */
function zhCreditText(m: ZhFile | ZhMeta | null): string {
  if (!m) return "汉译";
  const name = typeof m.translator === "string" ? m.translator.trim() : "";
  const yr = m.year !== undefined && m.year !== "" &&
      String(m.year).trim() !== ""
    ? String(m.year).trim()
    : "";
  let core = "";
  if (name && yr) core = `「${name}译（${yr}）」`;
  else if (name) core = `「${name}译」`;
  else if (yr) core = `「${yr}」`;
  if (!core) return "汉译";
  const src = typeof (m as ZhMeta).source === "string"
    ? (m as ZhMeta).source!.trim()
    : "";
  const tail = [src, m.license ?? ""]
    .map((s) => s.trim())
    .filter(Boolean)
    .join(" · ");
  return tail ? `${core} ${tail}` : core;
}

/* ---------------- setup ---------------- */

export function setupTranslationLayer(
  work: CatalogWork,
  opts: {
    /** Reader controls bar — receives the segmented 英译|汉译 control. */
    controls: El;
    /** Node the credit caption slots before (the reading body). */
    anchor: () => El | null;
    /** Live reading body (rows carry data-ref). */
    getBody: () => El | null;
  },
): TlLayerHandle | null {
  const zhMeta = translationZhOf(work);
  if (!zhMeta) return null; // ← works without translationZh: ZERO DOM impact
  const files = (zhMeta.files as unknown[]).filter(
    (f): f is string => typeof f === "string",
  );
  if (!files.length) return null;
  // non-null alias: narrowing above doesn't reach hoisted function bodies
  const catalogMeta: ZhMeta = zhMeta;

  let mode: TlMode = storedMode(work.id);
  let gen = 0; // bumps per mode change; stale async syncs bail out
  let zhFileMeta: ZhFile | null | "unloaded" = "unloaded";
  let suppressed = false; // sidebar view owns the stream while true

  // -- segmented control (reuses .theme-ctl geometry via shared class) ------
  const wrap = el("span", "theme-ctl tl-ctl");
  wrap.setAttribute("role", "group");
  wrap.setAttribute("aria-label", "Translation layer");
  const btnEn = el("button", undefined, "英译") as HTMLButtonElement;
  const btnZh = el("button", undefined, "汉译") as HTMLButtonElement;
  btnEn.type = btnZh.type = "button";
  btnEn.title = "English translation layer";
  btnZh.title = "Chinese translation (汉译)";
  const paintCtl = (): void => {
    btnEn.setAttribute("aria-pressed", String(mode === "en"));
    btnZh.setAttribute("aria-pressed", String(mode === "zh"));
  };
  wrap.appendChild(btnEn);
  wrap.appendChild(btnZh);
  paintCtl();
  opts.controls.appendChild(wrap);

  // -- credit caption (lazy; hidden in en mode) ------------------------------
  let credit: El | null = null;
  const ensureCredit = (): El => {
    if (!credit) {
      credit = el("p", "tl-credit");
      credit.hidden = true;
      const anchor = opts.anchor();
      if (anchor?.parentNode) anchor.parentNode.insertBefore(credit, anchor);
    }
    return credit;
  };

  const paintCredit = (): void => {
    const c = ensureCredit();
    if (mode !== "zh") {
      c.hidden = true;
      c.classList.remove("tl-missing");
      return;
    }
    if (zhFileMeta === "unloaded") {
      c.hidden = true; // nothing loaded yet; sync() will fill it in
      return;
    }
    if (zhFileMeta === null) {
      // zh file unreachable (404/malformed): say so, stay quiet-styled
      c.hidden = false;
      c.classList.add("tl-missing");
      c.textContent =
        "汉译文件暂缺，本页各单元已回退英译。/ Chinese file unavailable — English shown per unit.";
      return;
    }
    c.hidden = false;
    c.classList.remove("tl-missing");
    c.textContent = zhCreditText(zhFileMeta);
    if (zhFileMeta.alignment === "partial") {
      c.title = "部分单元无汉译对应，已回退英译。";
    }
  };

  // -- row painter ------------------------------------------------------------
  function clearRow(row: HTMLElement): void {
    row.querySelector(":scope > .tl-line")?.remove();
    delete row.dataset.tl;
  }

  function paintRow(
    row: HTMLElement,
    zhMap: Map<string, string>,
    enMap: Map<string, string>,
  ): void {
    if (row.dataset.tl === "zh") return; // already painted this mode
    clearRow(row);
    const ref = row.dataset.ref ?? "";
    const zhText = ref ? zhMap.get(ref) : undefined;
    const line = el("div", "tl-line");
    if (zhText !== undefined && zhText.trim() !== "") {
      line.setAttribute("lang", "zh");
      line.textContent = zhText;
    } else {
      // no zh correspondence for this ref → English fallback + faint tag
      line.classList.add("tl-en-fallback");
      line.setAttribute("lang", "en");
      const enText = ref ? enMap.get(ref) : undefined;
      line.append(
        document.createTextNode(enText?.trim() ? enText : "—"),
        el("span", "tl-miss", "无汉译"),
      );
    }
    // sit directly beneath the source line, above the parse cards
    const parseRow = row.querySelector(":scope > .parse-row");
    if (parseRow) parseRow.before(line);
    else row.appendChild(line);
    row.dataset.tl = "zh";
  }

  async function sync(): Promise<void> {
    const body = opts.getBody();
    if (!body || !body.isConnected) return;
    const myGen = gen;
    if (suppressed) {
      // sidebar owns the translation stream — keep inline rows clean
      for (const row of Array.from(
        body.querySelectorAll<HTMLElement>('[data-tl="zh"]'),
      )) clearRow(row);
      return;
    }
    if (mode === "en") {
      for (const row of Array.from(
        body.querySelectorAll<HTMLElement>('[data-tl="zh"]'),
      )) clearRow(row);
      paintCredit();
      return;
    }
    // 汉译: lazy-load zh (first activation only; cached thereafter)
    const zhMap = await loadZh(files);
    if (myGen !== gen) return; // user flipped back meanwhile
    if (zhFileMeta === "unloaded") {
      zhFileMeta = await loadZhMeta(files, catalogMeta);
      if (myGen !== gen) return;
    }
    const rows = Array.from(
      body.querySelectorAll<HTMLElement>("[data-ref]"),
    );
    if (!zhMap) {
      // total miss: everything falls back; credit explains why
      for (const row of rows) paintRow(row, new Map(), new Map());
      paintCredit();
      return;
    }
    // English texts load only if at least one rendered unit lacks zh
    const missing = rows.some((r) => {
      const ref = r.dataset.ref ?? "";
      return !(zhMap.get(ref)?.trim());
    });
    const enMap = missing
      ? await loadEnTexts(enFilesOf(work))
      : new Map<string, string>();
    if (myGen !== gen) return;
    for (const row of rows) paintRow(row, zhMap, enMap);
    paintCredit();
  }

  async function pick(m: TlMode): Promise<void> {
    if (m === mode) return;
    mode = m;
    gen += 1;
    storeMode(work.id, m);
    paintCtl();
    await sync();
  }
  btnEn.addEventListener("click", () => void pick("en"));
  btnZh.addEventListener("click", () => void pick("zh"));

  if (mode === "zh") void sync(); // persisted choice restored lazily

  return {
    sync,
    setSuppressed(b: boolean): void {
      suppressed = b;
      void sync(); // repaint inline rows (clears them while suppressed)
    },
  };
}

/** Existing English translation files of a work (may be absent). */
function enFilesOf(work: CatalogWork): string[] {
  const t = (work as { translation?: { files?: unknown } }).translation;
  const files = t && typeof t === "object" ? t.files : undefined;
  return Array.isArray(files)
    ? files.filter((f): f is string => typeof f === "string")
    : [];
}

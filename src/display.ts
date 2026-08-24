// Display-script preferences: TWO independent toggles (IAST / Devanagari),
// Persisted in localStorage under "interlinear-sanskrit.display" as
// {"iast":bool,"deva":bool}. Legacy values still honored: the old
// single-toggle string ("iast"/"dev") and the transitional ".scripts"
// object both map onto the new pair on first read.
// Invariant: at least one script is always on — turning the last one off
// auto-enables the other.
//
// Legacy migration: the old single-toggle key
//   "interlinear-sanskrit.display" ("iast" | "dev")
// maps to {iast:on,deva:off} resp. {iast:off,deva:on} on first read.
//
// Rendering contract (see render.ts): units register their token pairs in a
// registry; applyScriptDisplay() rebuilds every registered .unit-scripts
// block in place — parse rows are NOT touched, so layout/packing is reused.

import { devToIast, iastToDev, isDevanagari } from "./translit";
import { isKnown } from "./vocab";
import { stripAccents } from "./api";

export type ScriptKey = "iast" | "deva";
export interface ScriptPrefs {
  iast: boolean;
  deva: boolean;
}

const KEY = "interlinear-sanskrit.display";
// transitional object form stored here before the key merge
const LEGACY_SCRIPTS_KEY = "interlinear-sanskrit.scripts";
const LEGACY_STRING_KEY = "interlinear-sanskrit.display.legacy-string";

let cache: ScriptPrefs | null = null;
const listeners = new Set<() => void>();

function load(): ScriptPrefs {
  if (cache) return cache;
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      try {
        const p = JSON.parse(raw);
        if (typeof p === "object" && p !== null &&
            ("iast" in p || "deva" in p)) {
          cache = normalize({ iast: !!p.iast, deva: !!p.deva });
          return cache;
        }
      } catch { /* fall through to legacy shapes */ }
    }
    // transitional object form (pre-merge)
    const scriptsRaw = localStorage.getItem(LEGACY_SCRIPTS_KEY);
    if (scriptsRaw) {
      try {
        const p = JSON.parse(scriptsRaw);
        cache = normalize({ iast: !!p.iast, deva: !!p.deva });
        return cache;
      } catch { /* ignore */ }
    }
    // legacy single-toggle STRING lived under this very key before the
    // object format: "iast" -> {iast:on,deva:off}; "dev" -> inverse
    const legacy = localStorage.getItem(KEY);
    if (legacy === "dev") {
      cache = { iast: false, deva: true };
      return cache;
    }
    if (legacy === "iast") {
      cache = { iast: true, deva: false };
      return cache;
    }
    void LEGACY_STRING_KEY;
    cache = { iast: true, deva: false };
    return cache;
  } catch {
    cache = { iast: true, deva: false };
    return cache;
  }
}

function normalize(p: ScriptPrefs): ScriptPrefs {
  if (!p.iast && !p.deva) p.deva = true; // invariant: ≥1 always on
  return { iast: !!p.iast, deva: !!p.deva };
}

export function scriptPrefs(): ScriptPrefs {
  return { ...load() };
}

export function setScriptPrefs(next: Partial<ScriptPrefs>): void {
  const cur = load();
  const merged = normalize({ iast: next.iast ?? cur.iast, deva: next.deva ?? cur.deva });
  cache = merged;
  try {
    localStorage.setItem(KEY, JSON.stringify(merged));
  } catch { /* degrade silently */ }
  applyScriptDisplay();
  listeners.forEach((cb) => cb());
}

export function onScriptPrefsChange(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

/** Rebuild every registered unit-scripts block from its stored tokens. */
export function applyScriptDisplay(): void {
  const mode = load();
  document.body.classList.toggle("both-scripts", mode.iast && mode.deva);
  document.body.classList.toggle("dev-primary", mode.deva);
  for (const el of [...registry.keys()]) {
    if (!el.isConnected) {
      registry.delete(el);
      continue;
    }
    rebuild(el);
  }
}

/** True when the string contains Devanagari-block characters. */
export function isDevanagariStr(s: string): boolean {
  return isDevanagari(s);
}

/**
 * Per-token display conversion with DIRECTION DETECTION:
 *   target "deva" + source already IAST  -> iastToDev(token)
 *   target "iast" + source already Deva  -> devToIast(token)
 *   otherwise unchanged.
 * Mixed units resolve each token independently.
 */
export function disp(
  token: string,
  targetMode?: ScriptKey,
): string {
  const target = targetMode ?? (scriptPrefs().deva ? "deva" : "iast");
  if (target === "deva" && !isDevanagariStr(token)) return iastToDev(token);
  if (target === "iast" && isDevanagariStr(token)) return devToIast(token);
  return token;
}

// --- registry ---------------------------------------------------------------
type Tokens = {
  deva: string[];
  speakers: boolean[];
  onWord?: (i: number, sp: HTMLElement) => void;
  /** Work language tag ("pi"): tokens ship as IAST Latin and are shown
   *  as-is — no IAST→Devanagari conversion, Devanagari row suppressed. */
  lang?: string;
};
const registry = new Map<HTMLElement, Tokens>();

export function registerUnitScripts(
  el: HTMLElement,
  tokens: Tokens,
): void {
  registry.set(el, tokens);
  rebuild(el);
}

export function unregisterUnitScripts(el: HTMLElement): void {
  registry.delete(el);
}

function rebuild(el: HTMLElement): void {
  const t = registry.get(el);
  if (!t) return;
  const prefs = load();
  // Pali works render Roman-only regardless of script prefs (the tokens are
  // already IAST; converting would fabricate Devanagari nobody asked for).
  const forceIast = t.lang === "pi";
  el.replaceChildren();
  el.classList.toggle("dual", prefs.iast && prefs.deva && !forceIast);
  const mkSpan = (
    i: number,
    w: string,
    speaker: boolean,
    cls: string,
  ): HTMLElement => {
    const sp = document.createElement("span");
    sp.className = cls + (speaker ? " speaker" : "");
    sp.dataset.orig = w;
    // vocab dimming survives rebuilds
    if (document.body.classList.contains("vocab-highlight") &&
        isKnown(stripAccents(w))) {
      sp.classList.add("vk");
    }
    const targetScript = cls.includes("deva") ? "deva" : "iast";
    sp.textContent = forceIast ? w : disp(w, targetScript);
    if (!speaker && t.onWord) {
      sp.addEventListener("click", () => t.onWord!(i, sp));
    }
    return sp;
  };
  const rows: Array<{ on: boolean; cls: string }> = [
    { on: prefs.deva, cls: "sline deva-line" },
    { on: prefs.iast, cls: "sline iast-line" },
  ];
  // Dual mode: each token's cell stacks deva-then-iast, keeping both scripts
  // vertically paired per word while the whole line wraps naturally.
  // Single mode: one script line per cell.
  let activeRows = forceIast
    ? rows.filter((r) => r.cls.includes("iast"))
    : rows.filter((r) => r.on);
  if (!activeRows.length) activeRows = [rows[1]]; // pi + IAST pref off
  // Per-token CELLS: one inline-flex column per word, stacking this token's
  // active script lines (Devanagari above, IAST below). Cells flow inline
  // and WRAP at the viewport edge like ordinary text. The previous layout
  // (one big grid, grid-auto-flow:column) gave every unit a single
  // unwrappable row of columns — long verses blew far past the window width.
  t.deva.forEach((_, i) => {
    const cell = document.createElement("span");
    cell.className = "wcell";
    for (const r of activeRows) {
      cell.appendChild(mkSpan(i, t.deva[i],
        r.cls.includes("deva") && t.speakers[i], `${r.cls} w`));
    }
    el.appendChild(cell);
  });
}

/* ---------------- toolbar controls ---------------- */
export function scriptPrefControls(): HTMLElement {
  const wrap = document.createElement("span");
  wrap.className = "script-pref-controls";
  const mk = (key: ScriptKey, label: string): HTMLInputElement => {
    const cb = document.createElement("input") as HTMLInputElement;
    cb.type = "checkbox";
    cb.className = "script-pref";
    cb.dataset.script = key;
    cb.id = `script-${key}`;
    const lab = document.createElement("label");
    lab.htmlFor = cb.id;
    lab.appendChild(cb);
    lab.appendChild(document.createTextNode(label));
    wrap.appendChild(lab);
    return cb;
  };
  const iastCb = mk("iast", "IAST");
  const devaCb = mk("deva", "देवनागरी");
  const paint = (): void => {
    const p = load();
    iastCb.checked = p.iast;
    devaCb.checked = p.deva;
  };
  iastCb.addEventListener("change", () =>
    setScriptPrefs({ iast: iastCb.checked }));
  devaCb.addEventListener("change", () =>
    setScriptPrefs({ deva: devaCb.checked }));
  paint();
  const unsub = onScriptPrefsChange(paint);
  // detach on route teardown is unnecessary: controls live in the toolbar
  void unsub;
  return wrap;
}

// repaint once at import so pre-render content follows stored prefs
if (typeof document !== "undefined") {
  queueMicrotask(() => applyScriptDisplay());
}

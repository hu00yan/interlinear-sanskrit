// Display-script preferences: TWO independent toggles (IAST / Devanagari),
// persisted in localStorage under "interlinear-sanskrit.scripts".
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

const KEY = "interlinear-sanskrit.scripts";
const LEGACY_KEY = "interlinear-sanskrit.display";

let cache: ScriptPrefs | null = null;
const listeners = new Set<() => void>();

function load(): ScriptPrefs {
  if (cache) return cache;
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const p = JSON.parse(raw);
      const prefs = normalize({
        iast: !!p.iast,
        deva: !!p.deva,
      });
      cache = prefs;
      return prefs;
    }
    // legacy single-toggle migration
    const legacy = localStorage.getItem(LEGACY_KEY);
    cache =
      legacy === "dev" ? { iast: false, deva: true } :
      legacy === "iast" ? { iast: true, deva: false } :
      { iast: true, deva: false };
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
  el.replaceChildren();
  el.classList.toggle("dual", prefs.iast && prefs.deva);
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
    sp.textContent = disp(w, targetScript);
    if (!speaker && t.onWord) {
      sp.addEventListener("click", () => t.onWord!(i, sp));
    }
    return sp;
  };
  const rows: Array<{ on: boolean; cls: string }> = [
    { on: prefs.deva, cls: "sline deva-line" },
    { on: prefs.iast, cls: "sline iast-line" },
  ];
  // Dual mode: grid-auto-flow:column + two template rows — appending
  // deva-then-iast per word fills each column top-to-bottom, keeping word
  // cells vertically aligned across both script lines. Single mode: one row.
  const activeRows = rows.filter((r) => r.on);
  el.style.gridTemplateRows =
    `repeat(${activeRows.length}, auto)`;
  t.deva.forEach((_, i) => {
    for (const r of activeRows) {
      el.appendChild(mkSpan(i, t.deva[i],
        r.cls.includes("deva") && t.speakers[i], `${r.cls} w`));
    }
  });
  el.style.setProperty("--cols", String(t.deva.length));
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

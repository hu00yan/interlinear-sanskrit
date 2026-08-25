// Dual-script grammar tags: DCS feature strings arrive Devanagari-tagged
// ("लट्", "प्रथम", "बहु", "पुं"…). Every Devanagari tag renders STACKED with
// its IAST romanization beneath (devToIast at runtime) so readers of either
// script can scan parses; already-Latin tokens (UPOS names like "noun",
// digits, dialect/stemtype tags) pass through untouched.
//
// Shared by the reader parse cards + side panel (render.ts) and the home
// word-lookup box (lookup.ts). textContent-only — never innerHTML.
import { devToIast } from "./translit";

type El = HTMLElement;

/** True when the string contains Devanagari-block characters. */
export function isDevaStr(s: string): boolean {
  return /[\u0900-\u097f]/.test(s);
}

/** One grammar tag -> element: Devanagari with IAST beneath, or plain Latin. */
export function featTagEl(tok: string): El {
  const span = document.createElement("span");
  if (!isDevaStr(tok)) {
    span.className = "feat-tag";
    span.textContent = tok;
    return span;
  }
  span.className = "feat-tag feat-dual";
  const deva = document.createElement("span");
  deva.className = "feat-deva";
  deva.textContent = tok;
  const iast = document.createElement("span");
  iast.className = "feat-iast";
  iast.lang = "sa-Latn";
  iast.title = tok;
  iast.textContent = devToIast(tok);
  span.append(deva, iast);
  return span;
}

/**
 * Tokenize a joined feats string ("पुं;1;एक · Cpd") into display nodes,
 * preserving the " · " group separators; DCS ";"/whitespace/"|" separators
 * become single spaces between per-tag elements.
 */
export function featNodes(feats: string): Node[] {
  const out: Node[] = [];
  feats.split(" · ").forEach((seg, si) => {
    if (si > 0) out.push(document.createTextNode(" · "));
    seg.split(/[;\s|]+/).filter(Boolean).forEach((tok, ti) => {
      if (ti > 0) out.push(document.createTextNode(" "));
      out.push(featTagEl(tok));
    });
  });
  return out;
}

/** Build a .feats container filled with dual-script tag nodes. */
export function featsEl(feats: string, cls = "feats"): El {
  const d = document.createElement("div");
  d.className = cls;
  for (const n of featNodes(feats)) d.appendChild(n);
  return d;
}

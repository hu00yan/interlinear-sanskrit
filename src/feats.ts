// Dual-script grammar tags + lemmas: DCS feature strings arrive
// Devanagari-tagged ("लट्", "प्रथम", "बहु", "पुं"…). Every Devanagari tag
// renders STACKED with its IAST romanization, IAST FIRST/PRIMARY (heavier,
// full color) and the Devanagari beneath SECONDARY (muted, smaller):
//   लङ् -> laṅ (लङ्)
// so readers of either script can scan parses while IAST leads. Already-
// Latin tokens (UPOS names like "noun", digits, dialect/stemtype tags) pass
// through untouched. Lemmas get the same treatment via lemmaDualEl.
//
// Shared by the reader parse cards + side panel (render.ts), the home
// word-lookup box (lookup.ts) and the dictionary drawer (lexicon.ts).
// textContent-only — never innerHTML.
import { devToIast } from "./translit";

type El = HTMLElement;

/** True when the string contains Devanagari-block characters. */
export function isDevaStr(s: string): boolean {
  return /[\u0900-\u097f]/.test(s);
}

/** One grammar tag -> element: IAST over muted Devanagari, or plain Latin. */
export function featTagEl(tok: string): El {
  const span = document.createElement("span");
  if (!isDevaStr(tok)) {
    span.className = "feat-tag";
    span.textContent = tok;
    return span;
  }
  span.className = "feat-tag feat-dual";
  const iast = document.createElement("span");
  iast.className = "feat-iast";
  iast.lang = "sa-Latn";
  iast.textContent = devToIast(tok);
  const deva = document.createElement("span");
  deva.className = "feat-deva";
  deva.lang = "sa";
  deva.title = devToIast(tok);
  deva.textContent = tok;
  span.append(iast, deva);
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

/**
 * Lemma/headword display: BOTH scripts, IAST PRIMARY on top, Devanagari
 * secondary beneath. Non-Devanagari strings (Pali lemmas, SLP1 fallback
 * keys) render as-is in one span.
 */
export function lemmaDualEl(lemma: string): El {
  const span = document.createElement("span");
  if (!isDevaStr(lemma)) {
    span.className = "lemma";
    span.textContent = lemma || "?";
    return span;
  }
  span.className = "lemma lemma-stack";
  const iast = document.createElement("span");
  iast.className = "lemma-iast";
  iast.lang = "sa-Latn";
  iast.textContent = devToIast(lemma);
  const deva = document.createElement("span");
  deva.className = "lemma-deva";
  deva.lang = "sa";
  deva.textContent = lemma;
  span.append(iast, deva);
  return span;
}

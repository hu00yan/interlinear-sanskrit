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

/* ---------------- compact feature abbreviations (R2) ----------------
 * DCS shard feature strings arrive as Samsaadhanii-style Devanagari tags
 * ("पुं;1;एक", "लट्;उत्तम;एक;परस्मैपद"). Raw dumps are unreadable and tall;
 * parse presentation renders them as compact English abbreviations —
 * "m. sg. nom." / "pres. 3rd pl. act." — each abbr still STACKED over its
 * Devanagari original (bilingual per the existing .feat-dual convention).
 * Unmapped extras ("Cpd", "Gdv", stem types…) are NOT part of the compact
 * line: callers show them inside expanded detail only. */

const ABBR_CASE: Record<string, string> = {
  "1": "nom.", "2": "acc.", "3": "ins.", "4": "dat.", "5": "abl.",
  "6": "gen.", "7": "loc.", "\u0938\u092e\u094d\u092c\u094b\u0927\u0928":
    "voc.",
};
const ABBR_GENDER: Record<string, string> = {
  "\u092a\u0941\u0902": "m.",
  "\u0938\u094d\u0930\u0940": "f.",
  "\u0928\u092a\u0941\u0902": "n.",
};
const ABBR_NUMBER: Record<string, string> = {
  "\u090f\u0915": "sg.", "\u0926\u094d\u0935\u093f": "du.",
  "\u092c\u0939\u0941": "pl.",
};
const ABBR_PERSON: Record<string, string> = {
  "\u0909\u0924\u094d\u0924\u092e": "1st",
  "\u092e\u0927\u094d\u092f\u092e": "2nd",
  "\u092a\u094d\u0930\u0925\u092e": "3rd",
};
const ABBR_LAKARA: Record<string, string> = {
  "\u0932\u091f\u094d": "pres.",
  "\u0932\u0919\u094d": "impf.",
  "\u0932\u0943\u091f\u094d": "fut.",
  "\u0932\u0943\u0919\u094d": "cond.",
  "\u0932\u093f\u091f\u094d": "perf.",
  "\u0932\u0941\u0919\u094d": "aor.",
  "\u0932\u094b\u091f\u094d": "imperat.",
  "\u0935\u093f\u0927\u093f\u0932\u093f\u0919\u094d": "opt.",
};
const ABBR_VOICE: Record<string, string> = {
  "\u092a\u0930\u0938\u094d\u092e\u0948\u092a\u0926": "act.",
  "\u0906\u0924\u094d\u092e\u0928\u0947\u092a\u0926": "mid.",
};
/** POS code -> compact label (shard p field uses these four words). */
export function posAbbr(p: string): string {
  switch ((p || "").trim()) {
    case "noun": return "n.";
    case "verb": return "v.";
    case "part": return "ptcp.";
    case "indecl": return "indecl.";
    default: return p ? `${p}.` : "";
  }
}

export interface CompactFeats {
  /** Ordered display tags: tense · person · number · voice · gender · case */
  main: Array<{ ab: string; orig?: string }>;
  /** Unmapped extras (Cpd, Gdv, …) — expanded detail only. */
  extras: string[];
}

/** Classify + order one DCS f-string into compact display parts. */
export function parseDcsFeats(f: string): CompactFeats {
  const toks = (f ?? "").split(/[;\s|]+/).filter(Boolean);
  const main: CompactFeats["main"] = [];
  const extras: string[] = [];
  let tense: { ab: string; orig: string } | null = null;
  const person: Array<{ ab: string; orig?: string }> = [];
  const voice: Array<{ ab: string; orig?: string }> = [];
  const gender: Array<{ ab: string; orig?: string }> = [];
  const number: Array<{ ab: string; orig?: string }> = [];
  const kcase: Array<{ ab: string; orig?: string }> = [];
  for (const t of toks) {
    if (ABBR_LAKARA[t]) tense = { ab: ABBR_LAKARA[t], orig: t };
    else if (ABBR_PERSON[t]) person.push({ ab: ABBR_PERSON[t], orig: t });
    else if (ABBR_VOICE[t]) voice.push({ ab: ABBR_VOICE[t], orig: t });
    else if (ABBR_GENDER[t]) gender.push({ ab: ABBR_GENDER[t], orig: t });
    else if (ABBR_NUMBER[t]) number.push({ ab: ABBR_NUMBER[t], orig: t });
    // bare case digit first (no Devanagari original to mirror)
    else if (/^\d$/.test(t)) kcase.push({ ab: ABBR_CASE[t] ?? t });
    else if (ABBR_CASE[t]) kcase.push({ ab: ABBR_CASE[t], orig: t });
    else extras.push(t); // Cpd, Gdv, unmapped verbatim
  }
  // verb-ish first (tense leads); participles & nominals read
  // gender-number-case ("pres. act. m. pl. nom.", "m. sg. nom."),
  // finite verbs read person-number-voice ("pres. 3rd pl. act.");
  // bare case digits always land at the end
  if (tense) main.push(tense);
  if (gender.length) {
    main.push(...voice);
    main.push(...gender);
    main.push(...number);
  } else {
    main.push(...person);
    main.push(...number);
    main.push(...voice);
  }
  main.push(...kcase);
  return { main, extras };
}

/** One compact tag element: abbr primary, Devanagari original beneath. */
export function compactTagNode(t: { ab: string; orig?: string }): El {
  if (!t.orig) {
    const s = document.createElement("span");
    s.className = "feat-tag feat-abbr";
    s.textContent = t.ab;
    return s;
  }
  return featTagEl2(t.ab, t.orig);
}

function featTagEl2(abbr: string, orig: string): El {
  const span = document.createElement("span");
  span.className = "feat-tag feat-dual";
  const iast = document.createElement("span");
  iast.className = "feat-iast";
  iast.lang = "sa-Latn";
  iast.textContent = abbr;
  const d = document.createElement("span");
  d.className = "feat-deva";
  d.lang = "sa";
  d.title = abbr;
  d.textContent = orig;
  span.append(iast, d);
  return span;
}

/**
 * Compact .feats line for a shard analysis (p + f): POS label then
 * abbreviated inflection. Extras are returned via parseDcsFeats by the
 * caller for expanded detail; never rendered here.
 */
export function compactFeatsEl(p: string, f: string, cls = "feats"): El {
  const d = document.createElement("div");
  d.className = cls;
  const pos = posAbbr(p);
  const { main } = parseDcsFeats(f);
  if (pos) d.appendChild(compactTagNode({ ab: pos }));
  for (const t of main) {
    if (d.childNodes.length) d.appendChild(document.createTextNode(" "));
    d.appendChild(compactTagNode(t));
  }
  return d;
}

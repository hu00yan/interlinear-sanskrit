// Word-lookup box: the home-page slot that used to hold a static start-here
// card. Ported from greek-reader's lexicon drawer (src/lexicon.ts) and
// Sanskrit-adapted: type any Sanskrit/Pali word — Devanagari OR IAST — and
// morphological parse cards + Monier-Williams entries appear INLINE, no
// navigation. Script direction is auto-detected per keystroke:
//   Devanagari input -> used directly for the morphology surface index,
//                       devToIast for display/keys
//   Latin input      -> iastToDev for the morphology index, slp1KeyFor keys
//                       the MW gloss shards (same path as the reader panel)
// Results render with the shared dual-script grammar tags (feats.ts).
import { fetchJSON, loadMorph, stripAccents,
  type Parse } from "./api";
import { devToIast, iastToDev, isDevanagari, slp1KeyFor,
  slp1KeyVariants } from "./translit";
import { featsEl, featTagEl, lemmaDualEl } from "./feats";
import { compoundBlock } from "./compound";

type El = HTMLElement;
const el = (tag: string, cls?: string, text?: string): El => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text; // never innerHTML
  return e;
};

interface MwEntry {
  u: string; // headword as shipped (usually Devanagari)
  g: string; // English gloss
}

const MAX_PARSES = 8;
const MAX_MW = 6;

/** Monier-Williams entries for a query in either script: exact shard key
 *  first, then headwords beginning with the same key (prefix discovery,
 *  mirroring the Greek lexicon's LSJ headword scan). Misses return []. */
async function mwEntries(q: string, limit = MAX_MW): Promise<MwEntry[]> {
  const key = slp1KeyFor(q);
  if (!key || key.length < 2) return [];
  const letter = key[0]!;
  if (!/^[a-z]$/.test(letter)) return [];
  const shard = await fetchJSON<Record<string, { u?: string; g?: string }>>(
    `data/gloss/${letter}.json`,
  ).catch(() => null);
  if (!shard) return [];
  const out: MwEntry[] = [];
  const seen = new Set<string>();
  // exact key (+ sibilant-mirrored variants), lowercased like the shards
  for (const base of [key, ...slp1KeyVariants(key)]) {
    const k = base.toLowerCase();
    if (seen.has(k)) continue;
    seen.add(k);
    const hit = shard[k];
    if (hit && (hit.u || hit.g)) out.push({ u: hit.u ?? k, g: hit.g ?? "" });
  }
  if (!out.length) {
    // no exact headword — offer headwords that START with the query key
    for (const k of Object.keys(shard)
      .filter((k) => k.startsWith(key) && k !== key)
      .sort()
      .slice(0, limit)) {
      const hit = shard[k]!;
      out.push({ u: hit.u ?? k, g: hit.g ?? "" });
    }
  }
  return out.slice(0, limit);
}

/** Drop byte-identical duplicate analyses (DCS ships several). */
function dedupeParses(parses: Parse[]): Parse[] {
  const seen = new Set<string>();
  return parses.filter((p) => {
    const k = `${p.l}|${p.p}|${p.f}|${p.x}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

/** Lemma display: dual-script stacked (IAST primary + Devanagari beneath),
 *  plain when already Latin. */
function lemmaEl(lemma: string): El {
  return lemmaDualEl(lemma);
}

/** One parse card, mirroring the reader's collapsed best-parse card. */
function parseCardEl(p: Parse): El {
  const card = el("div", "pcard wl-card");
  const head = el("div", "cand-head");
  head.appendChild(lemmaEl(p.l || "?"));
  card.appendChild(head);
  const feats = [p.p, p.f, p.x].filter(Boolean).join(" · ");
  if (feats) card.appendChild(featsEl(feats));
  // inline DCS gloss when the shard ships one (MW section covers the rest)
  const g = (p as Parse & { g?: string }).g;
  if (g) card.appendChild(el("div", "gloss", g));
  // samāsa member mini-rows when this analysis carries a chain
  const comp = compoundBlock(p);
  if (comp) card.appendChild(comp);
  return card;
}

function mwCard(e: MwEntry): El {
  const card = el("div", "entry wl-card wl-mw");
  card.appendChild(el("span", "wl-src", "MW"));
  const head = el("div", "cand-head");
  head.appendChild(lemmaEl(e.u));
  card.appendChild(head);
  if (e.g) card.appendChild(el("div", "dict-gloss", e.g));
  return card;
}

async function run(
  raw: string,
  hint: El,
  results: El,
): Promise<void> {
  const q = raw.trim();
  results.replaceChildren();
  if (!q) {
    hint.textContent = "";
    return;
  }

  // both scripts accepted: normalize to Devanagari for the morphology
  // surface index; keep an IAST echo for the user
  const deva = isDevanagari(q) ? q : iastToDev(q);
  const iast = isDevanagari(q) ? devToIast(q) : stripAccents(q);
  hint.replaceChildren();
  hint.appendChild(featTagEl(deva)); // dual-script echo of the query

  const mySeq = ++seq;
  const [morphMap, mw] = await Promise.all([
    loadMorph([deva]).catch(() => new Map<string, Parse[]>()),
    mwEntries(q),
  ]);
  if (mySeq !== seq || !results.isConnected) return; // stale keystroke / torn down

  const parses = dedupeParses(morphMap.get(deva) ?? []);
  if (!parses.length && !mw.length) {
    results.appendChild(
      el("p", "lex-hint-empty",
        `No matches for “${q}” — try another spelling (${iast}).`),
    );
    return;
  }
  if (parses.length) {
    results.appendChild(el("h3", "wl-head",
      `解析 Grammar · ${parses.length} analysis${parses.length > 1 ? "es" : ""}`));
    for (const p of parses.slice(0, MAX_PARSES)) {
      results.appendChild(parseCardEl(p));
    }
  }
  if (mw.length) {
    results.appendChild(el("h3", "wl-head", "Monier-Williams"));
    for (const e of mw.slice(0, MAX_MW)) results.appendChild(mwCard(e));
  }
}

let seq = 0;

/**
 * The home word-lookup widget: input + live hint + inline result cards.
 * Self-contained; safe to discard with its route (no global state beyond
 * one module-level stale-response counter).
 */
export function wordLookupWidget(): El {
  const wrap = el("div", "word-lookup");
  wrap.setAttribute("role", "search");
  const input = el("input", "wl-input") as HTMLInputElement;
  input.type = "search";
  input.placeholder = "Word lookup — राम or rāma …";
  input.setAttribute("aria-label",
    "Word lookup: grammar analysis and Monier-Williams dictionary");
  input.autocomplete = "off";
  input.spellcheck = false;
  wrap.appendChild(input);

  const hint = el("p", "wl-hint");
  hint.setAttribute("aria-live", "polite");
  wrap.appendChild(hint);

  const results = el("div", "wl-results");
  wrap.appendChild(results);

  let debounce = 0;
  input.addEventListener("input", () => {
    window.clearTimeout(debounce);
    debounce = window.setTimeout(() => void run(input.value, hint, results), 140);
  });
  return wrap;
}

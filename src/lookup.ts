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
import { fetchJSON, loadGloss, loadMorph, stripAccents,
  type Gloss, type Parse } from "./api";
import { devToIast, iastToDev, isDevanagari, slp1KeyFor,
  slp1KeyVariants } from "./translit";
import { featTagEl, lemmaDualEl } from "./feats";
import { groupHeadEl } from "./group-ui";
import { MAX_VISIBLE_GROUPS, buildRankedGroups,
  clipGloss, type ParseGroup } from "./group";
import { compoundBlock, mwGlossFor } from "./compound";

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

/**
 * One grouped reading card, mirroring the reader's collapsed group-row:
 * `lemma abbr-feat-summary` + clipped MW gloss + samāsa block. The gloss
 * cell is filled by paintGroupGlosses-like async logic in renderGroupCards
 * (deterministic repeat-suppression across cards).
 */
function groupCardEl(g: ParseGroup): El {
  const card = el("div", "pcard wl-card cand-row");
  card.appendChild(groupHeadEl(g));
  card.appendChild(el("div", "gloss mw-gloss"));
  // samāsa member mini-rows when the representative analysis carries a chain
  const comp = compoundBlock(g.members[0]!);
  if (comp) card.appendChild(comp);
  return card;
}

/** Paint group-card glosses in order; clip ≤120 chars; show repeats once. */
function paintGroupCards(
  cards: Array<{ card: El; lemma: string }>,
): void {
  void Promise.all(
    cards.map((c) => mwGlossFor(c.lemma ?? "")),
  ).then((txts) => {
    const seen = new Set<string>();
    cards.forEach((c, i) => {
      const cell = c.card.querySelector(":scope > .mw-gloss") as El | null;
      if (!cell || !cell.isConnected) return;
      const t = txts[i];
      if (!t) {
        cell.remove();
        return;
      }
      const id = clipGloss(t).toLowerCase();
      if (seen.has(id)) {
        cell.remove(); // identical gloss already shown above
        return;
      }
      seen.add(id);
      cell.textContent = clipGloss(t);
    });
  });
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
  // preload lemma glosses BEFORE ranking: proper-name homograph demotion
  // needs the MW gloss text (ka -> "N. of Prajāpati" must not outrank the
  // interrogative particle reading)
  const glossMap = parses.length
    ? await loadGloss([...new Set(parses.map((p) => p.l))])
      .catch(() => new Map<string, Gloss>())
    : new Map<string, Gloss>();
  if (mySeq !== seq || !results.isConnected) return; // stale keystroke
  const groups = buildRankedGroups(parses, {
    glossOf: (l) => glossMap.get(stripAccents(l))?.g,
    form: deva,
  });
  if (!parses.length && !mw.length) {
    results.appendChild(
      el("p", "lex-hint-empty",
        `No matches for “${q}” — try another spelling (${iast}).`),
    );
    return;
  }
  if (groups.length) {
    results.appendChild(el("h3", "wl-head",
      `解析 Grammar · ${groups.length} reading${groups.length > 1 ? "s" : ""}`));
    const visibleGroups = groups.slice(0, MAX_VISIBLE_GROUPS);
    const cards = visibleGroups.map((g) => {
      const card = groupCardEl(g);
      results.appendChild(card);
      return { card, lemma: g.lemma };
    });
    paintGroupCards(cards);
    if (groups.length > MAX_VISIBLE_GROUPS) {
      results.appendChild(lookupExpandChip(groups, visibleGroups.length));
    }
  }
  if (mw.length) {
    results.appendChild(el("h3", "wl-head", "Monier-Williams"));
    for (const e of mw.slice(0, MAX_MW)) results.appendChild(mwCard(e));
  }
}

/**
 * 「另有 N 解」 chip for lookup readings beyond the collapsed cap: expands
 * IN PLACE, appending the remaining ranked group cards to the results list.
 */
function lookupExpandChip(groups: ParseGroup[], nVisible: number):
  HTMLButtonElement {
  const chip = el("button", "more-chip",
    `另有 ${groups.length - nVisible} 解`) as HTMLButtonElement;
  chip.lang = "zh";
  chip.type = "button";
  chip.title = `${groups.length} distinct readings — click to show all`;
  chip.setAttribute("aria-label",
    `${groups.length} readings; ${groups.length - nVisible} more — click to show all`);
  chip.addEventListener("click", () => {
    const list = chip.parentElement;
    if (!list) return;
    const cards = groups.slice(nVisible).map((g) => {
      const card = groupCardEl(g);
      list.insertBefore(card, chip);
      return { card, lemma: g.lemma };
    });
    paintGroupCards(cards);
    chip.remove();
  });
  return chip;
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
